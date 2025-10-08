# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile,Form, File
from bson import ObjectId
from auth.jwt_handler import get_current_user
from models.user import FoodFilter   # adjust path to your actual file
from database import get_db
from models.user import UserCreate
from database import db
from models.delivery import LocationUpdate,deliveryPhoneCreate
from auth.utils import create_access_token  # ✅ Import token creator
from datetime import datetime
from typing import List, Optional
import os
import uuid

router = APIRouter()
# ------------------- Upload Directories -------------------
UPLOAD_DIR_PROFILE = "uploads/profile"
UPLOAD_DIR_LICENSE = "uploads/licenses"

os.makedirs(UPLOAD_DIR_PROFILE, exist_ok=True)
os.makedirs(UPLOAD_DIR_LICENSE, exist_ok=True)


## ------------------- Create or Get Delivery User -------------------
@router.post("/delivery/users")
async def create_or_get_user(delivery: deliveryPhoneCreate):
    existing = await db["delivery_user"].find_one({"phone_number": delivery.phone_number})
    
    if existing:
        token = create_access_token({
            "sub": str(existing["_id"]),
            "role": "delivery"
        })
        return {
            "id": str(existing["_id"]),
            "message": "delivery user already exists",
            "token": token,
            "new": False  # user already exists
        }

    result = await db["delivery_user"].insert_one(delivery.dict())
    token = create_access_token({
        "sub": str(result.inserted_id),
        "role": "delivery"
    })
    return {
        "id": str(result.inserted_id),
        "message": "delivery user created successfully",
        "token": token,
        "new": True  # new user created
    }

@router.post("/delivery/update-location")
async def update_location(
    location: LocationUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "delivery":
        raise HTTPException(status_code=403, detail="Only delivery users can update location")

    delivery_id = ObjectId(current_user["_id"])

    # Update location directly in delivery_user
    update_data = {
        "location": {
            "type": "Point",
            "coordinates": [location.longitude, location.latitude]
        },
        "last_update": datetime.utcnow(),
        "status": False
    }

    result = await db["delivery_user"].update_one(
        {"_id": delivery_id},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Delivery user not found")

    return {"status": "success", "message": "Location updated"}


@router.post("/deliveryupdate")
async def update_delivery_profile(
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    vehicle: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    driving_license_front: Optional[UploadFile] = File(None),
    driving_license_back: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    print("Current user:", current_user)
    user_id = current_user["_id"]

    update_data = {}

    if name:
        update_data["name"] = name
    if email:
        update_data["email"] = email
    if vehicle:
        update_data["vehicle"] = vehicle

    # Profile photo
    if file is not None:
        contents = await file.read()
        photo_url = save_image_and_get_url(contents, file.filename)
        update_data["photo_url"] = photo_url

    # Driving license front
    if driving_license_front is not None:
        contents = await driving_license_front.read()
        front_url = save_image_and_get_url(contents, driving_license_front.filename)
        update_data["driving_license_front"] = front_url

    # Driving license back
    if driving_license_back is not None:
        contents = await driving_license_back.read()
        back_url = save_image_and_get_url(contents, driving_license_back.filename)
        update_data["driving_license_back"] = back_url

    # Save updates if any
    if update_data:
        await db["delivery_user"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

    return {
        "message": "Profile updated successfully",
        "updated": update_data
    }


#---------------------delivery ongoing ordeers------------#
@router.get("/ongoing/delivery/me")
async def get_my_orders(current_user: dict = Depends(get_current_user)):
    # Only delivery users can access
    if current_user.get("role") != "delivery":
        raise HTTPException(status_code=403, detail="Only delivery users can access")

    delivery_id = str(current_user["_id"])

    # Fetch orders assigned to this delivery boy with pending or picked status
    orders_cursor = db["orders"].find({
        "delivery_boy_id": delivery_id,
        "delivery_status": {"$in": ["assigned","picked"]}
    })

    orders = await orders_cursor.to_list(length=None)

    # Convert ObjectIds to strings for frontend
    for order in orders:
        order["_id"] = str(order["_id"])
        order["chef_id"] = str(order.get("chef_id", ""))
        order["delivery_boy_id"] = str(order.get("delivery_boy_id", ""))
        for item in order.get("items", []):
            item["food_id"] = str(item.get("food_id", ""))
            item["chef_id"] = str(item.get("chef_id", ""))

    return {"status": "success", "orders": orders}


# ------------------- Delivery Profile Update -------------------
def save_image_and_get_url(contents: bytes, filename: str = None) -> str:
    # Make sure folder exists
    os.makedirs(UPLOAD_DIR_PROFILE, exist_ok=True)

    # Create unique filename
    ext = filename.split(".")[-1] if filename else "jpg"
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR_PROFILE, unique_name)

    # Save file
    with open(filepath, "wb") as f:
        f.write(contents)

    # Return URL relative to static mount
    return f"/static/chefprofile/{unique_name}"



@router.get("/orders/delivery/me")
async def get_my_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "delivery":
        raise HTTPException(status_code=403, detail="Only delivery users can access")

    delivery_id = str(current_user["_id"])

    # Fetch orders assigned to this delivery boy with pending or picked status
    orders = await db["orders"].find({
        "delivery_boy_id": delivery_id,
        "delivery_status": {"$in": ["pending", "picked"]}
    }).to_list(length=None)

    # Convert ObjectIds to strings for frontend
    for order in orders:
        order["_id"] = str(order["_id"])
        order["chef_id"] = str(order["chef_id"])
        order["delivery_boy_id"] = str(order.get("delivery_boy_id", ""))
        for item in order.get("items", []):
            item["food_id"] = str(item["food_id"])
            item["chef_id"] = str(item["chef_id"])

    return {"status": "success", "orders": orders}
