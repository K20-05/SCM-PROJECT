from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.database.mongo import get_devices_collection
from backend.models.device_model import DeviceCreate, DeviceOut, DeviceUpdate


def _to_device_out(document: dict) -> DeviceOut:
    return DeviceOut(
        device_id=document["device_id"],
        name=document["name"],
        status=document["status"],
        created_at=document["created_at"],
    )


async def create_device(payload: DeviceCreate) -> DeviceOut:
    document = {
        "device_id": payload.device_id.strip(),
        "name": payload.name.strip(),
        "status": payload.status.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_deleted": False,
    }
    try:
        await get_devices_collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device id already exists") from exc
    return _to_device_out(document)


async def list_devices() -> list[DeviceOut]:
    devices = await get_devices_collection().find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(length=2000)
    return [_to_device_out(device) for device in devices]


async def get_device_by_device_id(device_id: str) -> DeviceOut:
    device = await get_devices_collection().find_one(
        {"device_id": device_id.strip(), "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _to_device_out(device)


async def update_device(device_id: str, payload: DeviceUpdate) -> DeviceOut:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    update_data["updated_at"] = datetime.now(timezone.utc)
    updated = await get_devices_collection().find_one_and_update(
        {"device_id": device_id.strip(), "is_deleted": {"$ne": True}},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _to_device_out(updated)


async def delete_device(device_id: str) -> None:
    deleted = await get_devices_collection().find_one_and_update(
        {"device_id": device_id.strip(), "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
        projection={"device_id": 1},
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
