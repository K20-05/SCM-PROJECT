from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from typing import Any

from backend.config.app_config import settings


def _json_serializer(value: dict[str, Any]) -> bytes:
    return json.dumps(value, default=str).encode("utf-8")


def build_device_event(
    *,
    device_id: str,
    battery_level: float,
    first_sensor_temperature: str | float,
    route_from: str,
    route_to: str,
    status: str = "active",
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "battery_level": battery_level,
        "first_sensor_temperature": str(first_sensor_temperature),
        "route_from": route_from,
        "route_to": route_to,
        "status": status,
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
    }


class DeviceDataProducer:
    def __init__(self, bootstrap_servers: str | None = None, topic: str | None = None):
        self.topic = topic or settings.kafka_device_topic
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer = None

    def _client(self):
        if self._producer is None:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                value_serializer=_json_serializer,
                key_serializer=lambda value: value.encode("utf-8"),
            )
        return self._producer

    def send_device_event(self, event: dict[str, Any]):
        device_id = str(event.get("device_id") or "")
        if not device_id:
            raise ValueError("device_id is required for Kafka device events")
        return self._client().send(self.topic, key=device_id, value=event)

    def flush(self) -> None:
        if self._producer is not None:
            self._producer.flush()

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close()
            self._producer = None


def publish_sample_event() -> dict[str, Any]:
    event = build_device_event(
        device_id="DEV-SAMPLE-001",
        battery_level=87.5,
        first_sensor_temperature="4.8C",
        route_from="Warehouse",
        route_to="Distribution Hub",
    )
    producer = DeviceDataProducer()
    try:
        producer.send_device_event(event).get(timeout=10)
        producer.flush()
    finally:
        producer.close()
    return event


def publish_random_events(interval_seconds: int = 10) -> None:
    routes = ["Newyork,USA", "Chennai, India", "Bengaluru, India", "London,UK"]
    producer = DeviceDataProducer()
    try:
        while True:
            route_from = random.choice(routes)
            route_to = random.choice(routes)
            if route_from == route_to:
                continue

            event = build_device_event(
                device_id=str(random.randint(1150, 1158)),
                battery_level=round(random.uniform(2.0, 5.0), 2),
                first_sensor_temperature=round(random.uniform(10, 40.0), 1),
                route_from=route_from,
                route_to=route_to,
            )
            producer.send_device_event(event)
            producer.flush()
            print(f"Sending: {event}")
            time.sleep(interval_seconds)
    finally:
        producer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Publish SCMXpertLite device data to Kafka.")
    parser.add_argument("--loop", action="store_true", help="continuously publish random device events")
    parser.add_argument("--interval", type=int, default=10, help="seconds between looped events")
    args = parser.parse_args()

    if args.loop:
        publish_random_events(interval_seconds=args.interval)
    else:
        sent = publish_sample_event()
        print(f"Published device event for {sent['device_id']} to {settings.kafka_device_topic}")
