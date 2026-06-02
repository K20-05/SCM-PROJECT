import asyncio
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backend.models.shipment_model import ShipmentCreate, ShipmentStatus, ShipmentUpdate
from backend.services import shipment_service


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

    def find(self, query: dict, _projection: dict):
        self.last_find_query = query
        collection = self

        class _Cursor:
            def __init__(self, docs: list[dict]):
                self.docs = docs

            async def to_list(self, length: int):
                return [doc for doc in self.docs if collection._matches(doc, query)][:length]

        return _Cursor(self.inserted_docs)

    async def find_one(self, query: dict, projection: dict | None = None):
        for doc in self.inserted_docs:
            if not self._matches(doc, query):
                continue
            if projection:
                return {key: doc[key] for key, include in projection.items() if include and key in doc}
            return dict(doc)
        return None

    async def find_one_and_update(self, query: dict, update: dict, return_document=None, projection: dict | None = None):
        for index, doc in enumerate(self.inserted_docs):
            if not self._matches(doc, query):
                continue
            patched = {**doc, **update.get("$set", {})}
            self.inserted_docs[index] = patched
            if projection == {"_id": 0}:
                return dict(patched)
            return patched
        return None

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, predicate) for predicate in expected):
                    return False
                continue
            if isinstance(expected, dict) and "$ne" in expected:
                if doc.get(key) == expected["$ne"]:
                    return False
                continue
            if doc.get(key) != expected:
                return False
        return True


def _payload() -> ShipmentCreate:
    return ShipmentCreate(
        shipment_number="SHIP-001",
        container_number="CONT-001",
        route_details="Chennai to Bangalore",
        goods_type="Electronics",
        device="Thermal tracker",
        expected_delivery_date=datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
        ph_number="PH-001",
        delivery_number="DEL-001",
        ndc_number="NDC-001",
        batch_id="BATCH-001",
        serial_number_of_goods="SER-001",
        shipment_description="Temperature monitored shipment",
    )


def test_create_shipment_sets_server_owned_fields(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    monkeypatch.setattr(shipment_service, "_generate_tracking_id", lambda: "SCM-ABC12345")

    result = asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))

    assert result.tracking_id == "SCM-ABC12345"
    assert result.status == ShipmentStatus.PENDING
    assert result.owner_id == "owner-1"
    assert fake_collection.inserted_docs[0]["is_deleted"] is False


def test_create_shipment_retries_on_duplicate_tracking_id(monkeypatch):
    fake_collection = _FakeShipmentsCollection(fail_once=True)
    ids = iter(["SCM-DUPL1111", "SCM-UNIQ2222"])
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    monkeypatch.setattr(shipment_service, "_generate_tracking_id", lambda: next(ids))

    result = asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))

    assert fake_collection.calls == 2
    assert result.tracking_id == "SCM-UNIQ2222"


def test_list_shipments_filters_soft_deleted_records(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    live = shipment_service.create_shipment(_payload(), owner_id="owner-1")
    result = asyncio.run(live)
    fake_collection.inserted_docs[0]["tracking_id"] = result.tracking_id
    fake_collection.inserted_docs.append({**fake_collection.inserted_docs[0], "tracking_id": "SCM-DELE0001", "is_deleted": True})

    shipments = asyncio.run(shipment_service.list_shipments())

    assert len(shipments) == 1
    assert fake_collection.last_find_query == {"is_deleted": {"$ne": True}}


def test_list_shipments_filters_to_current_user_for_user_role(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))
    asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-2"))

    shipments = asyncio.run(shipment_service.list_shipments({"_id": "owner-1", "role": "user"}))

    assert len(shipments) == 1
    assert shipments[0].owner_id == "owner-1"
    assert fake_collection.last_find_query == {"is_deleted": {"$ne": True}, "owner_id": "owner-1"}


def test_list_shipments_allows_admin_to_see_all_records(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))
    asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-2"))

    shipments = asyncio.run(shipment_service.list_shipments({"_id": "admin-1", "role": "admin"}))

    assert len(shipments) == 2
    assert fake_collection.last_find_query == {"is_deleted": {"$ne": True}}


def test_update_shipment_partial_sets_updated_at(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    created = asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))

    result = asyncio.run(
        shipment_service.update_shipment(
            created.tracking_id,
            ShipmentUpdate(route_details="Chennai to Pune", status=ShipmentStatus.IN_TRANSIT),
            {"_id": "owner-1", "role": "user"},
        )
    )

    assert result.route_details == "Chennai to Pune"
    assert result.status == ShipmentStatus.IN_TRANSIT
    assert "updated_at" in fake_collection.inserted_docs[0]


def test_delete_shipment_soft_delete(monkeypatch):
    fake_collection = _FakeShipmentsCollection()
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: fake_collection)
    created = asyncio.run(shipment_service.create_shipment(_payload(), owner_id="owner-1"))

    asyncio.run(shipment_service.delete_shipment(created.tracking_id))

    assert fake_collection.inserted_docs[0]["is_deleted"] is True
    assert "deleted_at" in fake_collection.inserted_docs[0]


def test_update_shipment_with_no_fields_returns_400():
    with_exception = None
    try:
        asyncio.run(shipment_service.update_shipment("SCM-EMPTY000", ShipmentUpdate(), {"_id": "owner-1", "role": "user"}))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 400
