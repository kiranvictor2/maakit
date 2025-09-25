# routers/chef.py
from fastapi import APIRouter, HTTPException,Depends
from fastapi.responses import FileResponse
from datetime import datetime
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


# @router.post("/chef/login")
# async def login_chef(data: ChefLoginRequest):
#     chef = await db["chef_user"].find_one({"phone_number": data.phone_number})
#     if not chef:
#         raise HTTPException(status_code=404, detail="Chef not found")

#     token_data = {
#         "sub": str(chef["_id"]),
#         "phone_number": chef["phone_number"],
#         "role": "chef"
#     }
#     access_token = create_access_token(data=token_data)

#     return {
#         "message": "Login successful",
#         "access_token": access_token,
#         "token_type": "bearer",
#         "chef": {
#             "id": str(chef["_id"]),
#             "phone_number": chef["phone_number"]
#         }
#     }

@router.post("/chef/login")
async def login_chef(data: ChefLoginRequest):
    chef = await db["chef_user"].find_one({"phone_number": data.phone_number})
    new_chef_flag = False
    chef_name = None

    if not chef:
        # Create a new chef
        # Try to get name from user collection
        user = await db["user"].find_one({"phone_number": data.phone_number})
        chef_name = user.get("name") if user else data.name if hasattr(data, "name") else None

        chef_data = {
            "phone_number": data.phone_number,
            "role": "chef",
            "name": chef_name,
        }
        result = await db["chef_user"].insert_one(chef_data)
        chef = await db["chef_user"].find_one({"_id": result.inserted_id})
    else:
        # If chef exists, get name from user if available
        user = await db["user"].find_one({"phone_number": data.phone_number})
        chef_name = user.get("name") if user else chef.get("name")

    # new_chef_flag: True if chef has a name, False if not
    new_chef_flag = False if chef_name else True

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
        "new": new_chef_flag,
        "chef": {
            "id": str(chef["_id"]),
            "phone_number": chef["phone_number"],
            "name": chef_name,
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

@router.put("/chef/item/update/{item_id}")
async def update_food_item(
    item_id: str,
    food_name: str = Form(...),
    food_style: str = Form(...),
    service_type: str = Form(...),
    food_type: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    off: float = Form(...),
    photo: UploadFile = File(None),  # Make it optional
    current_user: dict = Depends(get_current_user)
):
    food_item = await db["food_items"].find_one({"_id": ObjectId(item_id)})

    if not food_item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = {
        "food_name": food_name,
        "food_style": food_style,
        "food_type": food_type,
        "quantity": quantity,
        "price": price,
        "off": off,
        "service_type": service_type
    }

    if photo:
        contents = await photo.read()
        photo_url = save_image_and_get_url(contents, photo.filename)
        update_data["photo_url"] = photo_url

    await db["food_items"].update_one(
        {"_id": ObjectId(item_id)},
        {"$set": update_data}
    )

    return {"message": "Item updated successfully"}

# Delete food item
@router.delete("/chef/item/delete/{item_id}")
async def delete_food_item(item_id: str, current_user: dict = Depends(get_current_user)):
    chef_id = current_user["_id"]

    # Check if the item exists and belongs to the current chef
    existing_item = await db["food_items"].find_one({"_id": ObjectId(item_id), "chef_id": ObjectId(chef_id)})
    if not existing_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    # Delete the item
    await db["food_items"].delete_one({"_id": ObjectId(item_id), "chef_id": ObjectId(chef_id)})

    return {"message": "Food item deleted successfully", "item_id": item_id}

#-----------------------------------My food items---------------------------#
@router.get("/chef/items")
async def get_my_food_items(current_user: dict = Depends(get_current_user)):
    chef_id = current_user["_id"]

    items_cursor = db["food_items"].find({"chef_id": ObjectId(chef_id)})
    items = []
    async for item in items_cursor:
        items.append({
            "id": str(item["_id"]),
            "food_name": item["food_name"],
            "food_style": item["food_style"],
            "service_type": item["service_type"],
            "food_type": item["food_type"],
            "quantity": item["quantity"],
            "price": item["price"],
            "off": item["off"],
            "photo_url": item["photo_url"]
        })

    return {"items": items}




#-----------myorders------------------#
def convert_object_ids(orders: list):
    """Convert all ObjectId fields to strings for JSON serialization."""
    for o in orders:
        o["_id"] = str(o["_id"])
        for item in o.get("items", []):
            if "_id" in item:
                item["_id"] = str(item["_id"])
        if "address" in o and "_id" in o["address"]:
            o["address"]["_id"] = str(o["address"]["_id"])
    return orders


@router.get("/chef/orders/incoming")
async def get_incoming_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can view orders")
    chef_id = str(current_user["_id"])
    orders = await db["orders"].find({"chef_id": chef_id, "status": {"$in": ["new", "pending"]}}).to_list(length=None)
    print(orders)
    return {"status": "success", "orders": convert_object_ids(orders)}


@router.get("/chef/orders/ongoing")
async def get_ongoing_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can view orders")

    chef_id = str(current_user["_id"])
    
    # Fetch ongoing orders
    orders = await db["orders"].find({
        "chef_id": chef_id,
        "status": {"$in": ["chef_accepted", "preparing", "ready"]}
    }).to_list(length=None)

    # Fetch user details for each order
    for order in orders:
        user_id = order.get("user_id")
        delivery=order.get("delivery_boy_id")
        if user_id:
            user = await db["app_user"].find_one({"_id": ObjectId(user_id)})
            if user:
                order["user_details"] = {
                    "phone_number": user.get("phone_number"),
                    "role": user.get("role"),
                    "is_online": user.get("is_online"),
                    "last_seen": user.get("last_seen"),
                    "created_at": user.get("created_at"),
                    "location": user.get("location")
                }
        if delivery:
            delivery = await db["delivery_user"].find_one({"_id": ObjectId(delivery)})
            if delivery:
                order["delivery_user"] = {
                    "phone_number": delivery.get("phone_number"),
                
                }

    return {"status": "success", "orders": convert_object_ids(orders)}


@router.get("/chef/orders/completed")
async def get_completed_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can view orders")
    chef_id = str(current_user["_id"])
    orders = await db["orders"].find({"chef_id": chef_id, "status": {"$in": ["completed", "delivered"]}}).to_list(length=None)
    return {"status": "success", "orders": convert_object_ids(orders)}


@router.get("/chef/orders/all")
async def get_all_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can view orders")
    chef_id = str(current_user["_id"])
    orders = await db["orders"].find({"chef_id": chef_id}).to_list(length=None)
    return {"status": "success", "orders": convert_object_ids(orders)}


#update status-------------------------------#


@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update order status - only chefs can update order status"""
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can update order status")
    
    chef_id = str(current_user["_id"])
    
    # Validate the order exists and belongs to this chef
    try:
        order = await db["orders"].find_one({
            "_id": ObjectId(order_id),
            "chef_id": chef_id
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID format")
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or access denied")
    
    # Extract status from request body
    new_status = status_data.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    # Define valid status transitions
    valid_statuses = ["chef_accepted", "preparing", "ready", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Define status transition rules
    current_status = order.get("status", "pending")
    
    # Status transition validation
    valid_transitions = {
        "pending": ["chef_accepted", "cancelled"],
        "chef_accepted": ["preparing", "cancelled"],
        "preparing": ["ready", "cancelled"],
        "ready": ["completed", "cancelled"],
        "completed": [],  # Final state
        "cancelled": []   # Final state
    }
    
    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
        )
    
    # Prepare update data
    update_data = {
        "status": new_status,
        "updated_at": datetime.utcnow()
    }
    
    # Update chef_status based on the new status
    if new_status == "chef_accepted":
        update_data["chef_status"] = "accepted"
    elif new_status in ["preparing", "ready"]:
        update_data["chef_status"] = "accepted"
    elif new_status == "cancelled":
        update_data["chef_status"] = "cancelled"
    elif new_status == "completed":
        update_data["chef_status"] = "completed"
    
    # Auto-update delivery status for certain order statuses
    if new_status == "ready":
        # When order is ready, set delivery status to pending_assignment if not already assigned
        if order.get("delivery_status") in ["pending", "pending_assignment", None]:
            update_data["delivery_status"] = "pending_assignment"
    
    try:
        # Update the order
        result = await db["orders"].update_one(
            {"_id": ObjectId(order_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to update order status")
        
        # Fetch updated order
        updated_order = await db["orders"].find_one({"_id": ObjectId(order_id)})
        updated_order["_id"] = str(updated_order["_id"])
        
        # Optional: Send notification to user (implement as needed)
        # await notify_user_status_update(order["user_id"], order_id, new_status)
        
        return {
            "status": "success",
            "message": f"Order status updated to '{new_status}'",
            "order": updated_order
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update order: {str(e)}")







#--------------------individual order-------------------------#
@router.get("/orders/chef/{order_id}")
async def get_chef_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific order received by the chef."""
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can view this")

    try:
        oid = ObjectId(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db["orders"].find_one({"_id": oid, "chef_id": str(current_user["_id"])})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order["_id"] = str(order["_id"])
    if "address" in order and "_id" in order["address"]:
        order["address"]["_id"] = str(order["address"]["_id"])

    return {"status": "success", "order": order}
