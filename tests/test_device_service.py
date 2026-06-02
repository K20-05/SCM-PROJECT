import asyncio
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backend.models.device_model import DeviceCreate, DeviceStatus, DeviceUpdate
from backend.services import device_service


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    async def to_list(self, length: int):
        return self.docs[:length]


class _FakeDevicesCollection:
    def __init__(self):
        self.docs: list[dict] = []
        self.raise_duplicate = False

    async def insert_one(self, document: dict):
        if self.raise_duplicate:
            raise DuplicateKeyError("duplicate device id")
        self.docs.append(document)
        return {"inserted_id": "x"}

    def find(self, query: dict, _projection: dict):
        rows = self.docs
        if query.get("is_deleted", {}).get("$ne") is True:
            rows = [doc for doc in rows if doc.get("is_deleted") is not True]
        return _FakeCursor(rows)

    async def find_one(self, query: dict, projection: dict | None = None):
        for doc in self.docs:
            if doc.get("device_id") != query.get("device_id"):
                continue
            if query.get("is_deleted", {}).get("$ne") is True and doc.get("is_deleted") is True:
                continue
            if projection:
                return {k: v for k, v in doc.items() if projection.get(k, 1) != 0}
            return dict(doc)
        return None

    async def find_one_and_update(self, query: dict, update: dict, return_document=None, projection: dict | None = None):
        for idx, doc in enumerate(self.docs):
            if doc.get("device_id") != query.get("device_id"):
                continue
            if query.get("is_deleted", {}).get("$ne") is True and doc.get("is_deleted") is True:
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
            if doc.get("device_id") != query.get("device_id"):
                continue
            if query.get("is_deleted", {}).get("$ne") is True and doc.get("is_deleted") is True:
                continue
            del self.docs[idx]
            return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


def _seed_device(fake: _FakeDevicesCollection, *, deleted: bool = False):
    fake.docs.append(
        {
            "device_id": "DEV-1",
            "battery_level": 6.0,
            "first_sensor_temperature": "19.0 C",
            "route_from": "Mumbai, India",
            "route_to": "Louisville, USA",
            "timestamp": datetime(2026, 5, 20, 10, 19, tzinfo=timezone.utc),
            "status": DeviceStatus.AVAILABLE.value,
            "created_at": datetime(2026, 5, 20, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 5, 20, tzinfo=timezone.utc),
            "is_deleted": deleted,
        }
    )


def test_create_device_duplicate_returns_409(monkeypatch):
    fake = _FakeDevicesCollection()
    fake.raise_duplicate = True
    monkeypatch.setattr(device_service, "get_devices_collection", lambda: fake)

    with_exception = None
    try:
        asyncio.run(
            device_service.create_device(
                DeviceCreate(
                    device_id="DEV-1",
                    battery_level=6.0,
                    first_sensor_temperature="19.0 C",
                    route_from="Mumbai, India",
                    route_to="Louisville, USA",
                    timestamp=datetime(2026, 5, 20, 10, 19, tzinfo=timezone.utc),
                    status=DeviceStatus.AVAILABLE,
                ),
            )
        )
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 409


def test_update_device_with_empty_payload_returns_400(monkeypatch):
    fake = _FakeDevicesCollection()
    _seed_device(fake)
    monkeypatch.setattr(device_service, "get_devices_collection", lambda: fake)

    with_exception = None
    try:
        asyncio.run(device_service.update_device("DEV-1", DeviceUpdate()))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 400


def test_delete_device_soft_deletes_document(monkeypatch):
    fake = _FakeDevicesCollection()
    _seed_device(fake)
    monkeypatch.setattr(device_service, "get_devices_collection", lambda: fake)

    asyncio.run(device_service.delete_device("DEV-1"))

    assert len(fake.docs) == 1
    assert fake.docs[0]["is_deleted"] is True
    assert "deleted_at" in fake.docs[0]


def test_list_devices_hides_soft_deleted(monkeypatch):
    fake = _FakeDevicesCollection()
    _seed_device(fake, deleted=False)
    _seed_device(fake, deleted=True)
    fake.docs[1]["device_id"] = "DEV-2"
    monkeypatch.setattr(device_service, "get_devices_collection", lambda: fake)

    items = asyncio.run(device_service.list_devices())

    assert len(items) == 1
    assert items[0].device_id == "DEV-1"
