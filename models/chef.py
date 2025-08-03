# models/chef.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List

class ChefProfile(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    native_place: Optional[str]
    aadhar_number: Optional[str]
    food_styles: Optional[List[str]]  # list of food style names or IDs
    photo_url: Optional[str]  # image URL or path
    experience: Optional[int]
    specialty: Optional[List[str]]
    bio: Optional[str]

class ChefCreate(BaseModel):
    phone_number: str  # 📱 required
    role: str = "chef"
    profile: Optional[ChefProfile] = None

class ChefPhoneCreate(BaseModel):
    phone_number: str
    role: str = "chef"






class ChefLoginRequest(BaseModel):
    phone_number: str