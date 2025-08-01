# routers/chef.py
from fastapi import APIRouter, HTTPException
from models.chef import ChefCreate
from database import db
from models.chef import ChefLoginRequest
from auth.utils import create_access_token
from auth.jwt_handler import get_current_user

router = APIRouter()

@router.post("/chefs")
async def create_chef(chef: ChefCreate):
    exists = await db["chefs"].find_one({"phone": chef.phone})
    if exists:
        raise HTTPException(status_code=400, detail="Phone already registered")

    result = await db["chefs"].insert_one(chef.dict())
    return {"id": str(result.inserted_id), "message": "Chef created successfully"}


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

from fastapi import APIRouter, UploadFile, File, Form, Depends
@router.post("/chef/profile/update")
async def update_chef_profile(
    name: str = Form(...),
    email: str = Form(...),
    native_place: str = Form(...),
    aadhar_number: str = Form(...),
    food_styles: list[str] = Form(...),  # For multiple tags
    file: UploadFile = File(None),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["sub"]

    photo_url = None
    if file:
        contents = await file.read()
        # save image to S3, Cloudinary, or local folder
        photo_url = save_image_and_get_url(contents)

    # update DB
    await db["chefs"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "profile.name": name,
            "profile.email": email,
            "profile.native_place": native_place,
            "profile.aadhar_number": aadhar_number,
            "profile.food_styles": food_styles,
            "profile.photo_url": photo_url
        }}
    )

    return {"message": "Profile updated successfully"}