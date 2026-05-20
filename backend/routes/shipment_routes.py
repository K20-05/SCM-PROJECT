from fastapi import APIRouter, status
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
async def create_shipment_route(payload: ShipmentCreate):
    return await create_shipment(payload)


@router.get("", response_model=list[ShipmentOut])
async def list_shipments_route():
    return await list_shipments()


@router.patch("/{tracking_id}", response_model=ShipmentOut)
async def update_shipment_route(tracking_id: str, payload: ShipmentUpdate):
    return await update_shipment(tracking_id, payload)


@router.delete("/{tracking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment_route(tracking_id: str):
    return await delete_shipment_service(tracking_id)


@router.post("/{tracking_id}/assign-device", response_model=ShipmentOut)
async def assign_device_to_shipment_route(tracking_id: str, payload: DeviceAssignRequest):
    return await assign_device_to_shipment(tracking_id, payload)
