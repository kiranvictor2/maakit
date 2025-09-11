# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from auth.jwt_handler import get_current_user
from models.user import FoodFilter   # adjust path to your actual file
from database import get_db
from models.user import UserCreate
from database import db
from models.delivery import LocationUpdate,deliveryPhoneCreate
from auth.utils import create_access_token  # ✅ Import token creator
from datetime import datetime

router = APIRouter()

@router.post("/delivery/users")
async def create_or_get_user(delivery: deliveryPhoneCreate):
    existing = await db["delivery_user"].find_one({"phone_number": delivery.phone_number})
    
    if existing:
        token = create_access_token({
            "sub": str(existing["_id"]),  # unique identifier
            "role": "delivery"
        })
        return {
            "id": str(existing["_id"]),
            "message": "delivery user already exists",
            "token": token
        }

    # If not exists, create new
    result = await db["delivery_user"].insert_one(delivery.dict())
    token = create_access_token({
        "sub": str(result.inserted_id),
        "role": "delivery"
    })
    return {
        "id": str(result.inserted_id),
        "message": "delivery user created successfully",
        "token": token
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
