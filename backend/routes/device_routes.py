from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from auth.access_control import require_role
from auth.auth_deps import get_current_user
from backend.database.mongo import get_devices_collection
from backend.models.device_model import DeviceCreate, DeviceOut, DeviceUpdate


router = APIRouter(prefix="/api/devices", tags=["Devices"])


def _to_device_out(document: dict) -> DeviceOut:
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


@router.get("", response_model=list[DeviceOut])
async def list_devices(_current_user: dict = Depends(get_current_user)):
    devices = await get_devices_collection().find({}, {"_id": 0}).to_list(length=1000)
    return [_to_device_out(device) for device in devices]


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str, _current_user: dict = Depends(get_current_user)):
    device = await get_devices_collection().find_one({"device_id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _to_device_out(device)


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("admin"))])
async def create_device(payload: DeviceCreate):
    document = payload.model_dump()
    document["created_at"] = datetime.now(timezone.utc)
    try:
        await get_devices_collection().insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device ID already exists") from None
    return _to_device_out(document)


@router.patch("/{device_id}", response_model=DeviceOut, dependencies=[Depends(require_role("admin"))])
async def update_device(device_id: str, payload: DeviceUpdate):
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    updated = await get_devices_collection().find_one_and_update(
        {"device_id": device_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _to_device_out(updated)
