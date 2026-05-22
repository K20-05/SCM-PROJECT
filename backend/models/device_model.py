from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class DeviceAssignRequest(BaseModel):
    device_id: str = Field(min_length=1)


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1)
    battery_level: float
    first_sensor_temperature: str = Field(min_length=1)
    route_from: str = Field(min_length=1)
    route_to: str = Field(min_length=1)
    timestamp: datetime
    status: DeviceStatus = DeviceStatus.AVAILABLE


class DeviceOut(BaseModel):
    device_id: str
    battery_level: float
    first_sensor_temperature: str
    route_from: str
    route_to: str
    timestamp: datetime
    status: DeviceStatus
    created_at: datetime


class DeviceUpdate(BaseModel):
    battery_level: float | None = None
    first_sensor_temperature: str | None = Field(default=None, min_length=1)
    route_from: str | None = Field(default=None, min_length=1)
    route_to: str | None = Field(default=None, min_length=1)
    timestamp: datetime | None = None
    status: DeviceStatus | None = None
