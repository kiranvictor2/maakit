# routers/chef.py
from fastapi import APIRouter, HTTPException,Depends
from fastapi.responses import FileResponse

from bson import ObjectId
from typing import List, Optional
from models.chef import ChefCreate
from database import db
from models.chef import ChefLoginRequest,ChefPhoneCreate,LocationUpdate
from auth.utils import create_access_token
from auth.jwt_handler import get_current_user
from enum import Enum

router = APIRouter()

@router.post("/chefs")
async def create_or_get_chef(chef: ChefPhoneCreate):
    existing = await db["chef_user"].find_one({"phone_number": chef.phone_number})
    
    if existing:
        token = create_access_token({"phone": existing["phone_number"]})
        return {
            "id": str(existing["_id"]),
            "message": "Chef already exists",
            "token": token
        }

    # If not exists, create new
    result = await db["chef_user"].insert_one(chef.dict())
    token = create_access_token({"phone_number": chef.phone_number})
    return {
        "id": str(result.inserted_id),
        "message": "Chef created successfully",
        "token": token
    }


@router.post("/chef/login")
async def login_chef(data: ChefLoginRequest):
    chef = await db["chef_user"].find_one({"phone_number": data.phone_number})
    if not chef:
        raise HTTPException(status_code=404, detail="Chef not found")

    token_data = {
        "sub": str(chef["_id"]),
        "phone_number": chef["phone_number"],
        "role": "chef"
    }
    access_token = create_access_token(data=token_data)

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "chef": {
            "id": str(chef["_id"]),
            "phone_number": chef["phone_number"]
        }
    }






#location
@router.post("/cheflocation/update")
async def update_chef_location(
    location: LocationUpdate, 
    current_user: dict = Depends(get_current_user)
):
    chef_id = current_user.get("_id")
    
    result = await db["chef_user"].update_one(
        {"_id": ObjectId(chef_id)},
        {"$set": {
            "location": {
                "type": "Point",
                "coordinates": [location.longitude, location.latitude],
                "address": location.address
            }
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chef not found")
    
    return {"status": "success", "message": "Location updated"}














from fastapi import APIRouter, UploadFile, File, Form, Depends
import os
import uuid

UPLOAD_FOLDER = "uploads/chefprofile"  # folder for chef profile images

def save_image_and_get_url(contents: bytes, filename: str = None) -> str:
    # Make sure folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Create unique filename
    ext = filename.split(".")[-1] if filename else "jpg"
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    # Save file
    with open(filepath, "wb") as f:
        f.write(contents)

    # Return URL relative to static mount
    return f"/static/chefprofile/{unique_name}"

@router.get("/chef/profile/image/{filename}")
async def get_profile_image(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return {"error": "Image not found"}
    return FileResponse(file_path)



@router.post("/chef/profile/update")
async def update_chef_profile(
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    native_place: Optional[str] = Form(None),
    aadhar_number: Optional[str] = Form(None),
    food_styles: Optional[List[str]] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    print("Current user:", current_user)
    user_id = current_user["_id"]

    update_data = {}

    if name:
        update_data["name"] = name
    if email:
        update_data["email"] = email
    if native_place:
        update_data["native_place"] = native_place
    if aadhar_number:
        update_data["aadhar_number"] = aadhar_number
    if food_styles:
        update_data["food_styles"] = food_styles
    if file is not None:  # only if file uploaded
        contents = await file.read()
        photo_url = save_image_and_get_url(contents, file.filename)
        update_data["photo_url"] = photo_url

    if update_data:
        await db["chef_user"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

    return {"message": "Profile updated successfully", "updated": update_data}

#======================add iten ------------------


# Food styles Enum
class FoodStyleEnum(str, Enum):
    Andhra = "Andhra Style"
    Arunachal_Pradesh = "Arunachal Pradesh Style"
    Assam = "Assam Style"
    Bihar = "Bihar Style"
    Chattisgarh = "Chattisgarh Style"
    Delhi = "Delhi Style"
    Goa = "Goa Style"
    Gujarat = "Gujarat Style"
    Haryana = "Haryana Style"
    Himachal_Pradesh = "Himachal Pradesh Style"
    Jammu_Kashmir = "Jammu Kashmir Style"
    Jharkhand = "Jharkhand Style"
    Karnataka = "Karnataka Style"
    Kerala = "Kerala Style"
    Madhya_Pradesh = "Madhya Pradesh Style"
    Maharastrian = "Maharastrian Style"
    Meghalaya = "Meghalaya Style"
    Mizoram = "Mizoram Style"
    Nagaland = "Nagaland Style"
    Orissa = "Orissa Style"
    Punjabi = "Punjabi Style"
    Rajasthan = "Rajasthan Style"
    Sikkim = "Sikkim Style"
    Tamilian = "Tamilian Style"
    Telangana = "Telangana Style"
    Tripura = "Tripura Style"
    Uttrakhand = "Uttrakhand Style"
    Uttar_Pradesh = "Uttar Pradesh Style"
    West_Bengal = "West Bengal Style"


# Service type Enum
class ServiceTypeEnum(str, Enum):
    Breakfast = "Breakfast"
    Lunch = "Lunch"
    Dinner = "Dinner"


# Updated endpoint
@router.post("/chef/item/add")
async def add_food_item(
    food_name: str = Form(...),
    food_style: FoodStyleEnum = Form(...),
    service_type: ServiceTypeEnum = Form(...),  # <-- Enum validation
    food_type: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    off: float = Form(...),
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    chef_id = current_user["_id"]

    contents = await photo.read()
    photo_url = save_image_and_get_url(contents, photo.filename)

    food_item = {
        "chef_id": ObjectId(chef_id),
        "food_name": food_name,
        "food_style": food_style.value,
        "food_type": food_type,
        "quantity": quantity,
        "price": price,
        "off": off,
        "photo_url": photo_url,
        "service_type": service_type.value
    }

    result = await db["food_items"].insert_one(food_item)

    return {"message": "Food item added", "item_id": str(result.inserted_id)}


