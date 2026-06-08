from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.database.mongo import get_devices_collection, get_shipments_collection
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


def _is_admin(current_user: dict | None) -> bool:
    return current_user is None or current_user.get("role") in {"admin", "super_admin"}


async def _owned_device_ids(current_user: dict) -> list[str]:
    shipments = await get_shipments_collection().find(
        {
            "owner_id": str(current_user["_id"]),
            "device_id": {"$ne": None},
            "is_deleted": {"$ne": True},
        },
        {"_id": 0, "device_id": 1},
    ).to_list(length=1000)
    return sorted({shipment["device_id"] for shipment in shipments if shipment.get("device_id")})


async def list_devices(current_user: dict | None = None) -> list[DeviceOut]:
    query = {"is_deleted": {"$ne": True}}
    if not _is_admin(current_user):
        device_ids = await _owned_device_ids(current_user)
        if not device_ids:
            return []
        query["device_id"] = {"$in": device_ids}

    devices = await get_devices_collection().find(query, {"_id": 0}).to_list(length=1000)
    return [to_device_out(device) for device in devices]


async def get_device(device_id: str, current_user: dict | None = None) -> DeviceOut:
    if not _is_admin(current_user):
        owned_shipment = await get_shipments_collection().find_one(
            {
                "owner_id": str(current_user["_id"]),
                "device_id": device_id,
                "is_deleted": {"$ne": True},
            },
            {"_id": 1},
        )
        if not owned_shipment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this device")

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
