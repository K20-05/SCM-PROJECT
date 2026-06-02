from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.database.mongo import get_devices_collection
from backend.models.device_model import DeviceCreate, DeviceOut, DeviceUpdate


def to_device_out(document: dict) -> DeviceOut:
    return DeviceOut(
        device_id=document["device_id"],
        battery_level=document["battery_level"],
        first_sensor_temperature=document["first_sensor_temperature"],
        route_from=document["route_from"],
        route_to=document["route_to"],
        timestamp=document["timestamp"],
        status=document["status"],
        created_at=document["created_at"],
    )


async def list_devices() -> list[DeviceOut]:
    devices = await get_devices_collection().find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(length=1000)
    return [to_device_out(device) for device in devices]


async def get_device(device_id: str) -> DeviceOut:
    device = await get_devices_collection().find_one({"device_id": device_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return to_device_out(device)


async def create_device(payload: DeviceCreate) -> DeviceOut:
    document = payload.model_dump()
    document["created_at"] = datetime.now(timezone.utc)
    document["updated_at"] = datetime.now(timezone.utc)
    document["is_deleted"] = False
    try:
        await get_devices_collection().insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device ID already exists") from None
    return to_device_out(document)


async def update_device(device_id: str, payload: DeviceUpdate) -> DeviceOut:
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    updated = await get_devices_collection().find_one_and_update(
        {"device_id": device_id, "is_deleted": {"$ne": True}},
        {"$set": {**updates, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return to_device_out(updated)


async def delete_device(device_id: str) -> None:
    updated = await get_devices_collection().find_one_and_update(
        {"device_id": device_id, "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
