import asyncio
from datetime import datetime, timezone

from backend.database.mongo import (
    close_mongo_connection,
    connect_to_mongo,
    get_devices_collection,
    get_shipments_collection,
)


SHIPMENT_FIELD_MAP = {
    "sender": "shipment_number",
    "receiver": "container_number",
    "origin": "route_details",
    "destination": "goods_type",
    "expected_delivery": "expected_delivery_date",
    "weight_kg": "po_number",
}

DEVICE_FIELD_MAP = {
    "name": "route_from",
}


async def migrate_shipments() -> int:
    collection = get_shipments_collection()
    updated_count = 0
    cursor = collection.find({})

    async for doc in cursor:
        set_fields: dict = {}
        unset_fields: dict = {}

        for old_key, new_key in SHIPMENT_FIELD_MAP.items():
            if old_key not in doc:
                continue
            if new_key not in doc:
                if old_key == "weight_kg":
                    set_fields[new_key] = str(doc[old_key])
                else:
                    set_fields[new_key] = doc[old_key]
            unset_fields[old_key] = ""

        if set_fields or unset_fields:
            set_fields["updated_at"] = datetime.now(timezone.utc)
            await collection.update_one({"_id": doc["_id"]}, {"$set": set_fields, "$unset": unset_fields})
            updated_count += 1

    return updated_count


async def migrate_devices() -> int:
    collection = get_devices_collection()
    updated_count = 0
    cursor = collection.find({})

    async for doc in cursor:
        set_fields: dict = {}
        unset_fields: dict = {}

        for old_key, new_key in DEVICE_FIELD_MAP.items():
            if old_key not in doc:
                continue
            if new_key not in doc:
                set_fields[new_key] = doc[old_key]
            unset_fields[old_key] = ""

        # Seed required new keys if missing so reads do not fail.
        set_fields.setdefault("battery_level", float(doc.get("battery_level", 0.0)))
        set_fields.setdefault("first_sensor_temperature", doc.get("first_sensor_temperature", "0.0 C"))
        set_fields.setdefault("route_to", doc.get("route_to", "unknown"))
        set_fields.setdefault("timestamp", doc.get("timestamp", datetime.now(timezone.utc)))

        if set_fields or unset_fields:
            set_fields["updated_at"] = datetime.now(timezone.utc)
            await collection.update_one({"_id": doc["_id"]}, {"$set": set_fields, "$unset": unset_fields})
            updated_count += 1

    return updated_count


async def main() -> None:
    await connect_to_mongo()
    try:
        shipment_updates = await migrate_shipments()
        device_updates = await migrate_devices()
        print(f"Shipments migrated: {shipment_updates}")
        print(f"Devices migrated: {device_updates}")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
