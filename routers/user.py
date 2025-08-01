# routers/user.py
from fastapi import APIRouter, HTTPException
from models.user import UserCreate
from database import db
from models.user import LoginRequest
from auth.utils import create_access_token  # ✅ Import token creator
router = APIRouter()

@router.post("/users")
async def create_user(user: UserCreate):
    exists = await db["app_user"].find_one({"phone": user.phone})
    if exists:
        raise HTTPException(status_code=400, detail="Phone already exists")

    result = await db["app_user"].insert_one(user.dict())
    return {"id": str(result.inserted_id), "message": "User created"}




@router.post("/login")
async def login_user(data: LoginRequest):
    user = await db["app_user"].find_one({"phone_number": data.phone_number})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token_data = {
        "sub": str(user["_id"]),
        "phone_number": user["phone_number"],
        "role": "user"
    }
    access_token = create_access_token(data=token_data)

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "phone_number": user["phone_number"]
        }
    }
