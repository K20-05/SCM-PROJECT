from datetime import date

from fastapi import APIRouter, Depends, Query, status
from auth.access_control import require_role
from auth.auth_deps import get_current_user
from backend.models.device_model import DeviceAssignRequest
from backend.models.shipment_model import ShipmentCreate, ShipmentOut, ShipmentStatus, ShipmentUpdate
from backend.services.shipment_service import (
    ShipmentFilters,
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
async def list_shipments_route(
    current_user: dict = Depends(get_current_user),
    container_number: str | None = Query(default=None),
    status_filter: ShipmentStatus | None = Query(default=None, alias="status"),
    expected_delivery_date: date | None = Query(default=None),
    mine: bool = Query(default=False),
):
    filters = ShipmentFilters(
        container_number=container_number,
        status=status_filter,
        expected_delivery_date=expected_delivery_date,
    )
    return await list_shipments(current_user, filters, mine_only=mine)


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
async def assign_device_to_shipment_route(
    tracking_id: str,
    payload: DeviceAssignRequest,
    _current_user: dict = Depends(require_role("admin")),
):
    return await assign_device_to_shipment(tracking_id, payload)
