from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShipmentCreate(BaseModel):
    sender: str = Field(min_length=1)
    receiver: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    weight_kg: float = Field(gt=0)
    expected_delivery: datetime


class ShipmentOut(BaseModel):
    tracking_id: str
    sender: str
    receiver: str
    origin: str
    destination: str
    weight_kg: float
    expected_delivery: datetime
    status: ShipmentStatus
    owner_id: str
    created_at: datetime


class ShipmentUpdate(BaseModel):
    sender: str | None = Field(default=None, min_length=1)
    receiver: str | None = Field(default=None, min_length=1)
    origin: str | None = Field(default=None, min_length=1)
    destination: str | None = Field(default=None, min_length=1)
    weight_kg: float | None = Field(default=None, gt=0)
    expected_delivery: datetime | None = None
    status: ShipmentStatus | None = None


class ShipmentInDB(ShipmentOut):
    pass
