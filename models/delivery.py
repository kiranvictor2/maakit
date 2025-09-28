from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class deliveryPhoneCreate(BaseModel):
    phone_number: str
    role: str = "delivery"

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float

class DeliveryProfileCreate(BaseModel):
    name: str
    email: EmailStr
    vehicle: str
    photo_url: str | None = None
    driving_license_front: str | None = None
    driving_license_back: str | None = None