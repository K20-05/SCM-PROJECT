from fastapi import APIRouter, Depends, status
from auth.access_control import require_role
from backend.auth import get_current_user
from backend.models.device_model import DeviceAssignRequest
from backend.models.shipment_model import ShipmentCreate, ShipmentOut, ShipmentUpdate
from backend.services.shipment_service import (
    assign_device_to_shipment,
    create_shipment,
    delete_shipment as delete_shipment_service,
    list_shipments,
    update_shipment,
)


router = APIRouter(prefix="/api/shipments", tags=["Shipments"])


@router.post("", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED)
async def create_shipment_route(payload: ShipmentCreate, current_user: dict = Depends(get_current_user)):
    return await create_shipment(payload, owner_id=str(current_user["_id"]))


@router.get("", response_model=list[ShipmentOut])
async def list_shipments_route():
    return await list_shipments()


@router.patch("/{tracking_id}", response_model=ShipmentOut)
async def update_shipment_route(
    tracking_id: str,
    payload: ShipmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    return await update_shipment(tracking_id, payload, current_user)


@router.delete("/{tracking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment_route(
    tracking_id: str,
    _current_user: dict = Depends(require_role("admin")),
):
    return await delete_shipment_service(tracking_id)


@router.post("/{tracking_id}/assign-device", response_model=ShipmentOut)
async def assign_device_to_shipment_route(tracking_id: str, payload: DeviceAssignRequest):
    return await assign_device_to_shipment(tracking_id, payload)
