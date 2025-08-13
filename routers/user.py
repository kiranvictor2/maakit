# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from auth.jwt_handler import get_current_user

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

@router.get("/items/style/{food_style}")
async def get_items_by_style(food_style: str):
    food_style = food_style.strip()
    items = await db["food_items"].find({
        "food_style": {"$regex": f"\\s*{food_style}\\s*", "$options": "i"}
    }).to_list(length=None)

    for item in items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    return {"total": len(items), "items": items}




@router.get("/items/type/{food_type}")
async def get_items_by_type(food_type: str):
    food_type = food_type.strip()
    items = await db["food_items"].find({
        "food_type": {"$regex": f"\\s*{food_type}\\s*", "$options": "i"}
    }).to_list(length=None)

    for item in items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    return {"total": len(items), "items": items}

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict."""
    return {
        "id": str(doc["_id"]),
        "food_style": doc["food_style"],
        "image_url": doc.get("image_url")
    }

@router.get("/all-food-styles/")
async def get_all_food_styles():
    cursor = db["food_styles"].find({})
    styles = []
    async for doc in cursor:
        styles.append(serialize_doc(doc))
    return styles

