# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile,Form, File, Body
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

@router.get("/deliveryme")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    # Convert ObjectId to string for JSON serialization
    current_user["_id"] = str(current_user["_id"])
    
    return current_user

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
        "delivery_status": {"$in": ["assigned", "picked"]}
    })

    orders = await orders_cursor.to_list(length=None)

    enriched_orders = []

    for order in orders:
        order["_id"] = str(order["_id"])
        order["chef_id"] = str(order.get("chef_id", ""))
        order["delivery_boy_id"] = str(order.get("delivery_boy_id", ""))
        order["user_id"] = str(order.get("user_id", ""))  # Ensure user_id is string

        # Convert item IDs
        for item in order.get("items", []):
            item["food_id"] = str(item.get("food_id", ""))
            item["chef_id"] = str(item.get("chef_id", ""))

        # Fetch chef info
        chef = await db["chef_user"].find_one({"_id": ObjectId(order["chef_id"])})
        if chef:
            order["chef"] = {
                "name": chef.get("name"),
                "phone": chef.get("phone_number"),
                "location": chef.get("location"),
                "profile_pic": chef.get("photo_url"),
            }
        else:
            order["chef"] = {
                "name": "Unknown",
                "phone": None,
                "location": None,
                "profile_pic": None,
            }

        # Fetch customer info
        customer = await db["app_user"].find_one({"_id": ObjectId(order["user_id"])})
        if customer:
            order["customer"] = {
                "name": customer.get("name"),
                "phone": customer.get("phone_number"),
                "email": customer.get("email"),
                "location": customer.get("location"),
            }
        else:
            order["customer"] = {
                "name": "Unknown",
                "phone": None,
                "email": None,
                "location": None,
            }

        enriched_orders.append(order)

    return {"status": "success", "orders": enriched_orders}





# order status
from bson import ObjectId, errors
@router.get("/orderstatus/{order_id}")
async def get_order(order_id: str, current_user: dict = Depends(get_current_user)):

    # Only allow ObjectId if it's valid
    try:
        oid = ObjectId(order_id) if len(order_id) == 24 else None
    except errors.InvalidId:
        oid = None

    query = {"_id": oid} if oid else {"_id": order_id}  # fallback to string ID if not ObjectId

    # Fetch the order
    order = await db["orders"].find_one(query)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Delivery boy check
    if current_user.get("role") == "delivery" and str(order.get("delivery_boy_id")) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="You cannot access this order")

    # Convert IDs to strings for JSON
    for key in ["_id", "chef_id", "delivery_boy_id", "user_id"]:
        if key in order:
            order[key] = str(order[key])

    # Items conversion
    for item in order.get("items", []):
        item["food_id"] = str(item.get("food_id", ""))
        item["chef_id"] = str(item.get("chef_id", ""))

    # Chef info
    chef = None
    if order.get("chef_id"):
        try:
            chef = await db["chef_user"].find_one({"_id": ObjectId(order["chef_id"])})
        except errors.InvalidId:
            chef = None
    order["chef"] = {
        "name": chef.get("name") if chef else "Unknown",
        "phone": chef.get("phone_number") if chef else None,
        "location": chef.get("location") if chef else None,
        "profile_pic": chef.get("photo_url") if chef else None,
    }

    # Customer info
    customer = None
    if order.get("user_id"):
        try:
            customer = await db["app_user"].find_one({"_id": ObjectId(order["user_id"])})
        except errors.InvalidId:
            customer = None
    order["customer"] = {
        "name": customer.get("name") if customer else "Unknown",
        "phone": customer.get("phone_number") if customer else None,
        "email": customer.get("email") if customer else None,
        "location": customer.get("location") if customer else None,
    }

    return {"status": "success", "order": order}


# status update delivery boy
@router.put("/orderdeliveryupdate/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str = Body(..., embed=True),  # JSON body: {"status": "picked"}
    current_user: dict = Depends(get_current_user)
):
    # Only delivery boys can access
    if current_user.get("role") != "delivery":
        raise HTTPException(status_code=403, detail="Only delivery users can update status")

    # Validate ObjectId
    try:
        oid = ObjectId(order_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    # Fetch the order
    order = await db["orders"].find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ensure order is assigned to this delivery boy
    if str(order.get("delivery_boy_id")) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="You cannot update this order")

    # Allowed status updates
    allowed_statuses = ["assigned", "picked", "delivered"]
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {allowed_statuses}")

    update_data = {"delivery_status": status}

    # If delivery completed, mark the overall order as completed
    if status == "delivered":
        update_data["status"] = "completed"

    # Update order document
    await db["orders"].update_one(
        {"_id": oid},
        {"$set": update_data}
    )

    return {
        "status": "success",
        "order_id": str(order["_id"]),
        "new_delivery_status": status,
        "new_order_status": update_data.get("status", order.get("status"))
    }

#---------------------DELIVEERY BOY ORDER HISTORY-----------------#
# delivery boy order tracking
@router.get("/deliveryboy/orders")
async def get_deliveryboy_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "delivery":
        raise HTTPException(status_code=403, detail="Only delivery boys can access this endpoint")

    delivery_boy_id = str(current_user["_id"])

    # Fetch all orders assigned to this delivery boy
    orders = await db["orders"].find({"delivery_boy_id": delivery_boy_id}).sort("created_at", -1).to_list(length=None)

    ongoing_orders = []
    past_orders = []

    for order in orders:
        order["_id"] = str(order["_id"])
        order["user_id"] = str(order["user_id"])
        order["chef_id"] = str(order["chef_id"])
        order["delivery_boy_id"] = str(order["delivery_boy_id"])

        # Fetch customer details
        user = await db["users"].find_one({"_id": ObjectId(order["user_id"])})
        order["customer"] = {
            "name": user.get("name") if user else "Unknown",
            "phone": user.get("phone") if user else None
        }

        # Fetch chef details
        chef = await db["chef_user"].find_one({"_id": ObjectId(order["chef_id"])})
        order["chef"] = {
            "name": chef.get("name") if chef else "Unknown",
            "profile_pic": chef.get("photo_url") if chef else None,
            "location": chef.get("location") if chef else None
        }

        # Categorize based on delivery status
        delivery_status = order.get("delivery_status", "pending")

        if delivery_status in ["assigned", "picked_up", "out_for_delivery"]:
            ongoing_orders.append(order)
        elif delivery_status in ["delivered", "cancelled"]:
            past_orders.append(order)

    return {
        "status": "success",
        "ongoing_orders": ongoing_orders,
        "past_orders": past_orders
    }

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
        "delivery_status": {"$in": ["pending", "picked","assigned"]}
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




# Track individual order by order ID
@router.get("/deliveryordertrack/{order_id}")
async def track_order(order_id: str):
    # if current_user["role"] != "user":
    #     raise HTTPException(status_code=403, detail="Only users can access this endpoint")

    # user_id = str(current_user["_id"])

    # Fetch the specific order for this user
    order = await db["orders"].find_one({"_id": ObjectId(order_id)})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order["_id"] = str(order["_id"])
    order["user_id"] = str(order["user_id"])
    order["delivery_boy_id"] = str(order.get("delivery_boy_id", ""))

    # Fetch chef info
    chef = await db["chef_user"].find_one({"_id": ObjectId(order["chef_id"])})
    order["chef"] = {
        "name": chef.get("name") if chef else "Unknown",
        "profile_pic": chef.get("photo_url") if chef else None,
        "location": chef.get("location") if chef else None
    }

    # Fetch delivery boy info (if assigned)
    delivery_boy = None
    if order.get("delivery_boy_id"):
        delivery_boy = await db["delivery_user"].find_one({"_id": ObjectId(order["delivery_boy_id"])})

    order["delivery_boy_name"] = delivery_boy.get("name") if delivery_boy else "Not assigned"
    order["delivery_boy_location"] = delivery_boy.get("location") if delivery_boy else None

    # Convert item IDs
    for item in order.get("items", []):
        item["food_id"] = str(item["food_id"])
        item["chef_id"] = str(item["chef_id"])

    return {"status": "success", "order": order}