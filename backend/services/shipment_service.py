from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.database.mongo import get_devices_collection, get_shipments_collection
from backend.models.device_model import DeviceAssignRequest, DeviceStatus
from backend.models.shipment_model import ShipmentCreate, ShipmentOut, ShipmentStatus, ShipmentUpdate


def _generate_tracking_id() -> str:
    return f"SCM-{uuid4().hex[:8].upper()}"


def _shipment_identity_filter(identifier: str) -> dict:
    token = identifier.strip()
    predicates: list[dict] = [{"tracking_id": token}, {"tracking_id": token.upper()}]
    if ObjectId.is_valid(token):
        predicates.append({"_id": ObjectId(token)})
    return {"$or": predicates}


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
        device_id=document.get("device_id"),
        created_at=document["created_at"],
    )


async def create_shipment(payload: ShipmentCreate) -> ShipmentOut:
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
            "device_id": None,
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


async def list_shipments() -> list[ShipmentOut]:
    shipments = await get_shipments_collection().find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(length=2000)
    return [_to_shipment_out(shipment) for shipment in shipments]


async def update_shipment(tracking_id: str, payload: ShipmentUpdate) -> ShipmentOut:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    update_data["updated_at"] = datetime.now(timezone.utc)
    updated = await get_shipments_collection().find_one_and_update(
        {**_shipment_identity_filter(tracking_id), "is_deleted": {"$ne": True}},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return _to_shipment_out(updated)


async def delete_shipment(tracking_id: str) -> None:
    deleted = await get_shipments_collection().find_one_and_update(
        {**_shipment_identity_filter(tracking_id), "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
        projection={"tracking_id": 1},
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")


async def assign_device_to_shipment(tracking_id: str, payload: DeviceAssignRequest) -> ShipmentOut:
    device_id = payload.device_id.strip()
    shipments = get_shipments_collection()
    devices = get_devices_collection()

    shipment = await shipments.find_one({**_shipment_identity_filter(tracking_id), "is_deleted": {"$ne": True}})
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    if shipment.get("device_id"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shipment already has an assigned device")

    reserved_device = await devices.find_one_and_update(
        {"device_id": device_id, "status": DeviceStatus.AVAILABLE.value},
        {"$set": {"status": DeviceStatus.ASSIGNED.value, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not reserved_device:
        existing = await devices.find_one({"device_id": device_id}, {"_id": 0, "status": 1})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device is not available (current status: {existing.get('status')})",
        )

    updated = await shipments.find_one_and_update(
        {**_shipment_identity_filter(tracking_id), "is_deleted": {"$ne": True}, "device_id": None},
        {"$set": {"device_id": device_id, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        await devices.update_one(
            {"device_id": device_id},
            {"$set": {"status": DeviceStatus.AVAILABLE.value, "updated_at": datetime.now(timezone.utc)}},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment assignment changed concurrently. Please retry.",
        )
    return _to_shipment_out(updated)
