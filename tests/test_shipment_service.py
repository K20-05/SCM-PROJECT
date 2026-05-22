import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException

from backend.models.device_model import DeviceAssignRequest, DeviceStatus
from backend.models.shipment_model import ShipmentStatus, ShipmentUpdate
from backend.services import shipment_service


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    async def to_list(self, length: int):
        return self.docs[:length]


class _FakeShipmentsCollection:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.last_find_query: dict | None = None

    def find(self, query: dict, _projection: dict):
        self.last_find_query = query
        rows = [doc for doc in self.docs if doc.get("is_deleted") is not True]
        return _FakeCursor(rows)

    async def find_one(self, query: dict):
        for doc in self.docs:
            if doc.get("is_deleted") is True:
                continue
            if not _matches_identity(query.get("$or", []), doc):
                continue
            return dict(doc)
        return None

    async def find_one_and_update(self, query: dict, update: dict, return_document=None, projection: dict | None = None):
        for idx, doc in enumerate(self.docs):
            if query.get("is_deleted", {}).get("$ne") is True and doc.get("is_deleted") is True:
                continue
            if query.get("device_id") is None and doc.get("device_id") is not None:
                continue
            if not _matches_identity(query.get("$or", []), doc):
                continue
            patched = {**doc, **update.get("$set", {})}
            self.docs[idx] = patched
            if projection == {"_id": 0}:
                return dict(patched)
            if projection:
                return {k: patched[k] for k, include in projection.items() if include and k in patched}
            return dict(patched)
        return None

    async def delete_one(self, query: dict):
        for idx, doc in enumerate(self.docs):
            if not _matches_identity(query.get("$or", []), doc):
                continue
            del self.docs[idx]
            return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class _FakeDevicesCollection:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    async def find_one(self, query: dict, projection: dict | None = None):
        for doc in self.docs:
            if doc.get("device_id") != query.get("device_id"):
                continue
            if projection:
                return {k: v for k, v in doc.items() if projection.get(k, 1) != 0}
            return dict(doc)
        return None

    async def find_one_and_update(self, query: dict, update: dict, return_document=None):
        for idx, doc in enumerate(self.docs):
            if doc.get("device_id") != query.get("device_id"):
                continue
            if doc.get("status") != query.get("status"):
                continue
            patched = {**doc, **update.get("$set", {})}
            self.docs[idx] = patched
            return dict(patched)
        return None

    async def update_one(self, query: dict, update: dict):
        for idx, doc in enumerate(self.docs):
            if doc.get("device_id") == query.get("device_id"):
                self.docs[idx] = {**doc, **update.get("$set", {})}
                break


def _matches_identity(predicates: list[dict], doc: dict) -> bool:
    for pred in predicates:
        if "tracking_id" in pred and doc.get("tracking_id") == pred["tracking_id"]:
            return True
        if "_id" in pred and doc.get("_id") == pred["_id"]:
            return True
    return False


def _shipment_doc(tracking_id: str, *, deleted: bool = False, device_id: str | None = None):
    return {
        "_id": ObjectId(),
        "tracking_id": tracking_id,
        "shipment_number": "SHIP-1",
        "container_number": "CONT-1",
        "route_details": "X to Y",
        "goods_type": "Medicines",
        "device": "DEV-1",
        "expected_delivery_date": datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc),
        "po_number": "PO-1",
        "delivery_number": "DEL-1",
        "ndc_number": "NDC-1",
        "batch_id": "BATCH-1",
        "serial_number_of_goods": "SER-1",
        "shipment_description": "Test shipment",
        "status": ShipmentStatus.PENDING.value,
        "owner_id": "",
        "device_id": device_id,
        "created_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
        "is_deleted": deleted,
    }


def test_delete_shipment_hard_delete_removes_document(monkeypatch):
    shipments = _FakeShipmentsCollection([_shipment_doc("SCM-DEL00001")])
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: shipments)

    asyncio.run(shipment_service.delete_shipment("SCM-DEL00001"))

    assert len(shipments.docs) == 0


def test_delete_shipment_by_object_id_works(monkeypatch):
    doc = _shipment_doc("SCM-OBJ0001")
    shipments = _FakeShipmentsCollection([doc])
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: shipments)

    asyncio.run(shipment_service.delete_shipment(str(doc["_id"])))

    assert len(shipments.docs) == 0


def test_update_shipment_without_payload_returns_400():
    with_exception = None
    try:
        asyncio.run(shipment_service.update_shipment("SCM-EMPTY", ShipmentUpdate()))
    except HTTPException as exc:
        with_exception = exc
    assert with_exception is not None
    assert with_exception.status_code == 400


def test_assign_device_fails_when_device_not_available(monkeypatch):
    shipments = _FakeShipmentsCollection([_shipment_doc("SCM-ASN0001")])
    devices = _FakeDevicesCollection([{"device_id": "DEV-1", "status": DeviceStatus.ASSIGNED.value}])
    monkeypatch.setattr(shipment_service, "get_shipments_collection", lambda: shipments)
    monkeypatch.setattr(shipment_service, "get_devices_collection", lambda: devices)

    with_exception = None
    try:
        asyncio.run(
            shipment_service.assign_device_to_shipment(
                "SCM-ASN0001",
                DeviceAssignRequest(device_id="DEV-1"),
            )
        )
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 409
