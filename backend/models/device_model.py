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
    name: str = Field(min_length=1)
    status: DeviceStatus = DeviceStatus.AVAILABLE


class DeviceOut(BaseModel):
    device_id: str
    name: str
    status: DeviceStatus
    created_at: datetime


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    status: DeviceStatus | None = None
