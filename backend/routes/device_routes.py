from fastapi import APIRouter, Depends, status

from auth.access_control import require_role
from backend.models.device_model import DeviceCreate, DeviceOut, DeviceUpdate
from backend.services.device_service import (
    create_device,
    delete_device,
    get_device_by_device_id,
    list_devices,
    update_device,
)


router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def create_device_route(payload: DeviceCreate):
    return await create_device(payload)


@router.get("", response_model=list[DeviceOut])
async def list_devices_route():
    return await list_devices()


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device_route(device_id: str):
    return await get_device_by_device_id(device_id)


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device_route(device_id: str, payload: DeviceUpdate):
    return await update_device(device_id, payload)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_route(
    device_id: str,
    _current_user: dict = Depends(require_role("admin")),
):
    return await delete_device(device_id)
