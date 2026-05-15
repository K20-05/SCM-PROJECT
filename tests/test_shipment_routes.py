import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backend.models.shipment_model import ShipmentCreate, ShipmentStatus, ShipmentUpdate
from backend.routes import shipment_routes


class _FakeShipmentsCollection:
    def __init__(self, fail_once: bool = False):
        self.fail_once = fail_once
        self.inserted_docs: list[dict] = []
        self.calls = 0
        self.last_find_query: dict | None = None

    async def insert_one(self, document: dict):
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise DuplicateKeyError("duplicate tracking id")
        self.inserted_docs.append(document)
        return {"inserted_id": ObjectId()}

    def find(self, query: dict, _projection: dict):
        self.last_find_query = query
        class _Cursor:
            def __init__(self, docs: list[dict]):
                self.docs = docs

            async def to_list(self, length: int):
                return [doc for doc in self.docs if doc.get("is_deleted") is not True][:length]

        return _Cursor(self.inserted_docs)

    async def find_one_and_update(self, query: dict, update: dict, return_document=None, projection: dict | None = None):
        for index, doc in enumerate(self.inserted_docs):
            if doc.get("tracking_id") != query.get("tracking_id"):
                continue
            if query.get("is_deleted", {}).get("$ne") is True and doc.get("is_deleted") is True:
                continue
            patched = {**doc, **update.get("$set", {})}
            self.inserted_docs[index] = patched
            if projection:
                if projection == {"_id": 0}:
                    return dict(patched)
                result = {}
                for key, include in projection.items():
                    if key == "_id":
                        continue
                    if include and key in patched:
                        result[key] = patched[key]
                return result
            return patched
        return None


def test_create_shipment_sets_server_owned_fields(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_routes, "get_shipments_collection", lambda: fake_collection)
    monkeypatch.setattr(shipment_routes, "_generate_tracking_id", lambda: "SCM-ABC12345")

    payload = ShipmentCreate(
        sender="Alice",
        receiver="Bob",
        origin="Chennai",
        destination="Bangalore",
        weight_kg=25.5,
        expected_delivery=datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
    )

    result = asyncio.run(shipment_routes.create_shipment(payload))

    assert result.tracking_id == "SCM-ABC12345"
    assert result.status == ShipmentStatus.PENDING
    assert result.owner_id == ""
    assert fake_collection.inserted_docs[0]["status"] == ShipmentStatus.PENDING.value


def test_create_shipment_retries_on_duplicate_tracking_id(monkeypatch):
    fake_collection = _FakeShipmentsCollection(fail_once=True)
    ids = iter(["SCM-DUPL1111", "SCM-UNIQ2222"])
    monkeypatch.setattr(shipment_routes, "get_shipments_collection", lambda: fake_collection)
    monkeypatch.setattr(shipment_routes, "_generate_tracking_id", lambda: next(ids))

    payload = ShipmentCreate(
        sender="Warehouse A",
        receiver="Store B",
        origin="Hyderabad",
        destination="Pune",
        weight_kg=10.0,
        expected_delivery=datetime(2026, 5, 21, 9, 0, tzinfo=timezone.utc),
    )

    result = asyncio.run(shipment_routes.create_shipment(payload))

    assert fake_collection.calls == 2
    assert result.tracking_id == "SCM-UNIQ2222"


def test_list_shipments_returns_all(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    fake_collection.inserted_docs = [
        {
            "tracking_id": "SCM-AAAA1111",
            "sender": "A",
            "receiver": "B",
            "origin": "X",
            "destination": "Y",
            "weight_kg": 4.5,
            "expected_delivery": datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
            "status": "pending",
            "owner_id": "",
            "created_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            "is_deleted": False,
        },
        {
            "tracking_id": "SCM-DELE0001",
            "sender": "C",
            "receiver": "D",
            "origin": "M",
            "destination": "N",
            "weight_kg": 8.0,
            "expected_delivery": datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
            "status": "cancelled",
            "owner_id": "",
            "created_at": datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
            "is_deleted": True,
        }
    ]
    monkeypatch.setattr(shipment_routes, "get_shipments_collection", lambda: fake_collection)

    result = asyncio.run(shipment_routes.list_shipments())

    assert len(result) == 1
    assert result[0].tracking_id == "SCM-AAAA1111"
    assert fake_collection.last_find_query == {"is_deleted": {"$ne": True}}


def test_update_shipment_partial_sets_updated_at(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    fake_collection.inserted_docs = [
        {
            "tracking_id": "SCM-UPDT0001",
            "sender": "Old Sender",
            "receiver": "Old Receiver",
            "origin": "X",
            "destination": "Y",
            "weight_kg": 5.0,
            "expected_delivery": datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
            "status": "pending",
            "owner_id": "",
            "created_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            "is_deleted": False,
        }
    ]
    monkeypatch.setattr(shipment_routes, "get_shipments_collection", lambda: fake_collection)

    result = asyncio.run(
        shipment_routes.update_shipment(
            "SCM-UPDT0001",
            ShipmentUpdate(sender="New Sender", status=ShipmentStatus.IN_TRANSIT),
        )
    )

    assert result.sender == "New Sender"
    assert result.status == ShipmentStatus.IN_TRANSIT
    assert "updated_at" in fake_collection.inserted_docs[0]


def test_delete_shipment_soft_delete(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    fake_collection.inserted_docs = [
        {
            "tracking_id": "SCM-DEL00001",
            "sender": "A",
            "receiver": "B",
            "origin": "X",
            "destination": "Y",
            "weight_kg": 3.0,
            "expected_delivery": datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
            "status": "pending",
            "owner_id": "",
            "created_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            "is_deleted": False,
        }
    ]
    monkeypatch.setattr(shipment_routes, "get_shipments_collection", lambda: fake_collection)

    asyncio.run(shipment_routes.delete_shipment("SCM-DEL00001"))

    assert fake_collection.inserted_docs[0]["is_deleted"] is True
    assert "deleted_at" in fake_collection.inserted_docs[0]


def test_update_shipment_with_no_fields_returns_400():
    with_exception = None
    try:
        asyncio.run(shipment_routes.update_shipment("SCM-EMPTY000", ShipmentUpdate()))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 400
