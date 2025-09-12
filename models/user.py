# models/user.py
from pydantic import BaseModel, Field
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




class ReviewCreate(BaseModel):
    chef_id: str
    taste_rating: int = Field(..., ge=1, le=5)
    portion_rating: int = Field(..., ge=1, le=5)
    review_text: str


class Address(BaseModel):
    user_id: str  # Link to the user
    label: str
    flat_no: str
    landmark: str
    area: str
    coordinates: list  # [lon, lat]
    is_default: bool = False


# cart model
class CartItemRequest(BaseModel):
    food_id: str
    quantity: int