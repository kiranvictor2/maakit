from pydantic import BaseModel, Field
from typing import Optional

class deliveryPhoneCreate(BaseModel):
    phone_number: str
    role: str = "delivery"

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float