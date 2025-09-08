# models/user.py
from pydantic import BaseModel
from typing import Optional

class UserProfile(BaseModel):
    name: Optional[str]
    age: Optional[int]
    gender: Optional[str]

class UserCreate(BaseModel):
    phone: str
    role: str = "user"
    profile: Optional[UserProfile] = None




#location

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    address: str | None = None









class LoginRequest(BaseModel):
    phone_number: str


class userPhoneCreate(BaseModel):
    phone_number: str
    role: str = "chef"

from typing import List, Optional
from pydantic import BaseModel

class FoodFilter(BaseModel):
    food_styles: Optional[List[str]] = None
    service_types: Optional[List[str]] = None
    menu_types: Optional[List[str]] = None
    sort_by: Optional[str] = None