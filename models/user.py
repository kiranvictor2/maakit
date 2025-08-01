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

class LoginRequest(BaseModel):
    phone_number: str

