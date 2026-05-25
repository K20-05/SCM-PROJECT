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
    shipment_number: str = Field(min_length=1)
    container_number: str = Field(min_length=1)
    route_details: str = Field(min_length=1)
    goods_type: str = Field(min_length=1)
    device: str = Field(min_length=1)
    expected_delivery_date: datetime
    ph_number: str = Field(min_length=1)
    delivery_number: str = Field(min_length=1)
    ndc_number: str = Field(min_length=1)
    batch_id: str = Field(min_length=1)
    serial_number_of_goods: str = Field(min_length=1)
    shipment_description: str = Field(min_length=1)


class ShipmentOut(BaseModel):
    tracking_id: str
    shipment_number: str
    container_number: str
    route_details: str
    goods_type: str
    device: str
    expected_delivery_date: datetime
    ph_number: str
    delivery_number: str
    ndc_number: str
    batch_id: str
    serial_number_of_goods: str
    shipment_description: str
    status: ShipmentStatus
    owner_id: str
    device_id: str | None = None
    created_at: datetime


class ShipmentUpdate(BaseModel):
    shipment_number: str | None = Field(default=None, min_length=1)
    container_number: str | None = Field(default=None, min_length=1)
    route_details: str | None = Field(default=None, min_length=1)
    goods_type: str | None = Field(default=None, min_length=1)
    device: str | None = Field(default=None, min_length=1)
    expected_delivery_date: datetime | None = None
    ph_number: str | None = Field(default=None, min_length=1)
    delivery_number: str | None = Field(default=None, min_length=1)
    ndc_number: str | None = Field(default=None, min_length=1)
    batch_id: str | None = Field(default=None, min_length=1)
    serial_number_of_goods: str | None = Field(default=None, min_length=1)
    shipment_description: str | None = Field(default=None, min_length=1)
    status: ShipmentStatus | None = None


class ShipmentInDB(ShipmentOut):
    pass
