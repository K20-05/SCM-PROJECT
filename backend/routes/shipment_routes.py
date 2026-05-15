from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from backend.database.mongo import get_shipments_collection
from backend.models.shipment_model import ShipmentCreate, ShipmentOut, ShipmentStatus, ShipmentUpdate


router = APIRouter(prefix="/api/shipments", tags=["Shipments"])


def _generate_tracking_id() -> str:
    return f"SCM-{uuid4().hex[:8].upper()}"


def _to_shipment_out(document: dict) -> ShipmentOut:
    return ShipmentOut(
        tracking_id=document["tracking_id"],
        sender=document["sender"],
        receiver=document["receiver"],
        origin=document["origin"],
        destination=document["destination"],
        weight_kg=float(document["weight_kg"]),
        expected_delivery=document["expected_delivery"],
        status=document["status"],
        owner_id=str(document["owner_id"]),
        created_at=document["created_at"],
    )


@router.post("", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED)
async def create_shipment(payload: ShipmentCreate):
    shipments_collection = get_shipments_collection()
    for _ in range(5):
        shipment_document = {
            "tracking_id": _generate_tracking_id(),
            "sender": payload.sender,
            "receiver": payload.receiver,
            "origin": payload.origin,
            "destination": payload.destination,
            "weight_kg": payload.weight_kg,
            "expected_delivery": payload.expected_delivery,
            "status": ShipmentStatus.PENDING.value,
            "owner_id": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_deleted": False,
        }

        try:
            await shipments_collection.insert_one(shipment_document)
            return _to_shipment_out(shipment_document)
        except DuplicateKeyError:
            continue

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a unique tracking id. Please retry.",
    )


@router.get("", response_model=list[ShipmentOut])
async def list_shipments():
    shipments = await get_shipments_collection().find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(length=2000)
    return [_to_shipment_out(shipment) for shipment in shipments]


@router.patch("/{tracking_id}", response_model=ShipmentOut)
async def update_shipment(tracking_id: str, payload: ShipmentUpdate):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    update_data["updated_at"] = datetime.now(timezone.utc)
    updated = await get_shipments_collection().find_one_and_update(
        {"tracking_id": tracking_id, "is_deleted": {"$ne": True}},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return _to_shipment_out(updated)


@router.delete("/{tracking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment(tracking_id: str):
    deleted = await get_shipments_collection().find_one_and_update(
        {"tracking_id": tracking_id, "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
        projection={"tracking_id": 1},
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return None
