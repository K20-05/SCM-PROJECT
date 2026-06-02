from fastapi import APIRouter, Depends, status

from auth.access_control import require_role
from auth.auth_deps import get_current_user
from backend.models.device_model import DeviceCreate, DeviceOut, DeviceUpdate
from backend.services.device_service import (
    create_device as create_device_service,
    get_device as get_device_service,
    list_devices as list_devices_service,
    update_device as update_device_service,
)


router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(_current_user: dict = Depends(get_current_user)):
    return await list_devices_service()


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str, _current_user: dict = Depends(get_current_user)):
    return await get_device_service(device_id)


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("admin"))])
async def create_device(payload: DeviceCreate):
    return await create_device_service(payload)


@router.patch("/{device_id}", response_model=DeviceOut, dependencies=[Depends(require_role("admin"))])
async def update_device(device_id: str, payload: DeviceUpdate):
    return await update_device_service(device_id, payload)
