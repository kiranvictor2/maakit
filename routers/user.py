# routers/user.py
from fastapi import APIRouter, HTTPException
from models.user import UserCreate
from database import db
from models.user import LoginRequest,userPhoneCreate
from auth.utils import create_access_token  # ✅ Import token creator
router = APIRouter()

@router.post("/users")
async def create_or_get_user(chef: userPhoneCreate):
    existing = await db["app_user"].find_one({"phone_number": chef.phone_number})
    
    if existing:
        token = create_access_token({"phone": existing["phone_number"]})
        return {
            "id": str(existing["_id"]),
            "message": "user already exists",
            "token": token
        }

    # If not exists, create new
    result = await db["app_user"].insert_one(chef.dict())
    token = create_access_token({"phone_number": chef.phone_number})
    return {
        "id": str(result.inserted_id),
        "message": "user created successfully",
        "token": token
    }




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
