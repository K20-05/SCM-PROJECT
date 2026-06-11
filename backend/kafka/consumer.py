from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from backend.config.app_config import settings
from backend.database.mongo import (
    close_mongo_connection,
    connect_to_mongo,
    get_devices_collection,
    get_sensor_data_collection,
)


def parse_device_event(raw_value: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        payload = raw_value
    else:
        text = raw_value.decode("utf-8") if isinstance(raw_value, bytes) else raw_value
        payload = json.loads(text)

    device_id = str(payload.get("device_id") or "").strip()
    if not device_id:
        raise ValueError("Kafka device event is missing device_id")

    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return {
        "device_id": device_id,
        "battery_level": float(payload.get("battery_level", 0)),
        "first_sensor_temperature": str(payload.get("first_sensor_temperature", "")),
        "route_from": str(payload.get("route_from", "")),
        "route_to": str(payload.get("route_to", "")),
        "timestamp": timestamp,
        "status": str(payload.get("status") or "active"),
    }


async def persist_device_event(event: dict[str, Any]) -> None:
    timestamp = datetime.now(timezone.utc)
    normalized = parse_device_event(event)
    sensor_document = {
        **normalized,
        "recorded_at": timestamp,
        "source": "kafka",
    }
    await get_sensor_data_collection().insert_one(sensor_document)
    await get_devices_collection().update_one(
        {"device_id": normalized["device_id"]},
        {
            "$set": {
                **normalized,
                "updated_at": timestamp,
                "is_deleted": False,
            },
            "$setOnInsert": {"created_at": timestamp},
        },
        upsert=True,
    )


def _json_deserializer(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


async def consume_device_events() -> None:
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        settings.kafka_device_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        group_id=settings.kafka_consumer_group,
        value_deserializer=_json_deserializer,
        enable_auto_commit=True,
        auto_offset_reset="latest",
    )
    await connect_to_mongo()
    try:
        for message in consumer:
            await persist_device_event(message.value)
    finally:
        consumer.close()
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(consume_device_events())
