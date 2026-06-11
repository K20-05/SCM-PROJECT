import asyncio

from backend.kafka.consumer import parse_device_event, persist_device_event
from backend.kafka.producer import build_device_event


class _FakeCollection:
    def __init__(self):
        self.inserted = []
        self.updates = []

    async def insert_one(self, document: dict):
        self.inserted.append(document)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        self.updates.append({"query": query, "update": update, "upsert": upsert})


def test_build_and_parse_device_event_normalizes_payload():
    event = build_device_event(
        device_id="DEV-42",
        battery_level=91.2,
        first_sensor_temperature=5.4,
        route_from="Mumbai",
        route_to="Pune",
    )

    parsed = parse_device_event(event)

    assert parsed["device_id"] == "DEV-42"
    assert parsed["battery_level"] == 91.2
    assert parsed["first_sensor_temperature"] == "5.4"
    assert parsed["status"] == "active"


def test_parse_device_event_accepts_legacy_uppercase_payload():
    parsed = parse_device_event(
        {
            "Battery_Level": 3.8,
            "Device_ID": "1152",
            "First_Sensor_temperature": 27.4,
            "Route_From": "Chennai, India",
            "Route_To": "London,UK",
            "timestamp": "2026-06-11T12:00:00+00:00",
        }
    )

    assert parsed["device_id"] == "1152"
    assert parsed["battery_level"] == 3.8
    assert parsed["first_sensor_temperature"] == "27.4"
    assert parsed["route_from"] == "Chennai, India"
    assert parsed["route_to"] == "London,UK"


def test_persist_device_event_writes_sensor_and_upserts_device(monkeypatch):
    sensors = _FakeCollection()
    devices = _FakeCollection()
    monkeypatch.setattr("backend.kafka.consumer.get_sensor_data_collection", lambda: sensors)
    monkeypatch.setattr("backend.kafka.consumer.get_devices_collection", lambda: devices)

    asyncio.run(
        persist_device_event(
            {
                "device_id": "DEV-99",
                "battery_level": 77,
                "first_sensor_temperature": "6.1C",
                "route_from": "A",
                "route_to": "B",
            }
        )
    )

    assert sensors.inserted[0]["device_id"] == "DEV-99"
    assert sensors.inserted[0]["source"] == "kafka"
    assert devices.updates[0]["query"] == {"device_id": "DEV-99"}
    assert devices.updates[0]["upsert"] is True
