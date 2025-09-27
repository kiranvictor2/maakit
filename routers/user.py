# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from bson import ObjectId
from auth.jwt_handler import get_current_user
from models.user import FoodFilter   # adjust path to your actual file
from database import get_db
from models.user import UserCreate
from database import db
from models.user import LoginRequest,userPhoneCreate,LocationUpdate,ReviewCreate,CartItemRequest,Address
from auth.utils import create_access_token  # ✅ Import token creator
from datetime import datetime
import asyncio
import uuid

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
async def login_or_create_user(data: LoginRequest):
    # Try to find the user
    user = await db["app_user"].find_one({"phone_number": data.phone_number})

    # If not found, create a new one
    if not user:
        new_user = {
            "phone_number": data.phone_number,
            "role": "user",   # default role
            "created_at": datetime.utcnow(),
        }
        result = await db["app_user"].insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user

    # Prepare token payload
    token_data = {
        "sub": str(user["_id"]),
        "phone_number": user["phone_number"],
        "role": user.get("role", "user"),
    }
    access_token = create_access_token(data=token_data)

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "phone_number": user["phone_number"],
            "role": user.get("role", "user"),
        }
    }




@router.post("/userlocation/update")
async def update_location(
    location: LocationUpdate, 
    current_user: dict = Depends(get_current_user)
):
    # safer: use sub instead of _id
    user_id = current_user.get("_id")  

    result = await db["app_user"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "location": {
                "type": "Point",
                "coordinates": [location.longitude, location.latitude],
                "address": location.address
            }
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": "Location updated"}



















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




#breakfast #lunch snacks dinner

@router.get("/items/category/{food_type}/{category}")
async def get_items_by_type(
    food_type: str,
    category: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, gt=0, le=100, description="Maximum number of items to return")
):
    """
    Get food items by food style (regex) and service type (exact match).
    Supports pagination using skip and limit.
    """
    food_type = food_type.strip()
    category = category.strip()

    # Query MongoDB
    query = {
        "food_style": {"$regex": f"\\s*{food_type}\\s*", "$options": "i"},
        "service_type": category
    }

    items_cursor = db["food_items"].find(query).skip(skip).limit(limit)
    items = await items_cursor.to_list(length=limit)

    # Convert ObjectId to string
    for item in items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    # Return total count for frontend pagination
    total_count = await db["food_items"].count_documents(query)

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "items": items
    }   



#get filtered items

async def get_filtered_food_items(
    db,
    food_styles: list[str] = None,
    service_types: list[str] = None,
    menu_types: list[str] = None,
    sort_by: str = None
):
    filters = {}

    conditions = []

    # Food Style
    if food_styles:
        conditions.extend([
            {"food_style": {"$regex": f"\\s*{fs}\\s*", "$options": "i"}}
            for fs in food_styles
        ])

    # Service Type
    if service_types:
        conditions.extend([
            {"service_type": {"$regex": f"\\s*{st}\\s*", "$options": "i"}}
            for st in service_types
        ])

    # Menu Type
    if menu_types:
        conditions.extend([
            {"food_type": {"$regex": f"\\s*{mt}\\s*", "$options": "i"}}
            for mt in menu_types
        ])

    if conditions:
        filters["$and"] = conditions   # combine all conditions

    # Build query
    cursor = db["food_items"].find(filters)

    # Sort
    if sort_by and sort_by.lower() == "top rated":
        cursor = cursor.sort("rating", -1)

    # Return list
    items = await cursor.to_list(length=None)
    return items

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON serializable dict."""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, list):
            serialized[key] = [
                str(v) if isinstance(v, ObjectId) else v for v in value
            ]
        else:
            serialized[key] = value
    return serialized

@router.post("/filter-food")
async def filter_food(filter_data: FoodFilter, db=Depends(get_db)):
    items = await get_filtered_food_items(
        db,
        food_styles=filter_data.food_styles,
        service_types=filter_data.service_types,
        menu_types=filter_data.menu_types,
        sort_by=filter_data.sort_by
    )

    serialized_items = [serialize_doc(item) for item in items]

    return {"count": len(serialized_items), "items": serialized_items}








#-------------------------------------------------Near by --------------------------------------------------------#
@router.get("/chefs/nearby")
async def get_nearby_chefs(
    max_distance_m: int = 5000,  # default 5 km
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["_id"]

    # 1️⃣ Get current user location
    user = await db["app_user"].find_one({"_id": ObjectId(user_id)})
    if not user or "location" not in user:
        return {"status": "error", "message": "User location not set"}

    user_location = user["location"]["coordinates"]  # [longitude, latitude]

    # 2️⃣ Find nearby chefs with location
    projection_fields = {
        "id": 1,
        "name": 1,
        "location": 1,
        "address": 1,
        "photo_url":1,
    }


    nearby_chefs = await db["chef_user"].find(
        {
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": user_location
                    },
                    "$maxDistance": max_distance_m
                }
            }
        },
        projection=projection_fields
    ).to_list(100)

    nearby_chefs = [convert_objectid(c) for c in nearby_chefs]

    return {"status": "success", "chefs": nearby_chefs}

def convert_objectid(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc



#-----------------------------------------------------------------Near-by ----------------------------------------------------#
@router.get("/food/nearby")
async def get_nearby_chef_food(
    max_distance_m: int = 5000,  # default 5 km
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["_id"]

    # 1️⃣ Get current user location
    user = await db["app_user"].find_one({"_id": ObjectId(user_id)})
    if not user or "location" not in user:
        return {"status": "error", "message": "User location not set"}

    user_location = user["location"]["coordinates"]  # [longitude, latitude]

    # 2️⃣ Find nearby chefs
    nearby_chefs = await db["chef_user"].find({
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": user_location
                },
                "$maxDistance": max_distance_m
            }
        }
    }).to_list(100)

    if not nearby_chefs:
        return {"status": "success", "items": [], "message": "No nearby chefs found"}

    chef_ids = [c["_id"] for c in nearby_chefs]

    # 3️⃣ Get food items for those chefs
    food_items = await db["food_items"].find({
        "chef_id": {"$in": chef_ids}
    }).to_list(length=None)

    # Convert ObjectId to string
    for item in food_items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    return {"status": "success", "count": len(food_items), "items": food_items}




#--------------------------------------------------all fod of particulat chef-------------------------------#
@router.get("/food/by-chef/{chef_id}")
async def get_food_by_chef(chef_id: str):
    try:
        chef_obj_id = ObjectId(chef_id)
    except:
        return {"status": "error", "message": "Invalid chef_id"}

    # 1️⃣ Check if chef exists
    chef = await db["chef_user"].find_one({"_id": chef_obj_id})
    if not chef:
        return {"status": "error", "message": "Chef not found"}

    # 2️⃣ Get food items for that chef
    food_items = await db["food_items"].find({
        "chef_id": chef_obj_id
    }).to_list(length=None)

    # Convert ObjectId to string
    for item in food_items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    # 3️⃣ Group by service_type
    grouped_items = {
        "Breakfast": [],
        "Lunch": [],
        "Dinner": []
    }
    for item in food_items:
        stype = item.get("service_type", "Others").capitalize()
        if stype in grouped_items:
            grouped_items[stype].append(item)
        else:
            # If unexpected service_type comes, put under "Others"
            if "Others" not in grouped_items:
                grouped_items["Others"] = []
            grouped_items["Others"].append(item)

    return {
        "status": "success",
        "chef": {
            "_id": str(chef["_id"]),
            "name": chef.get("name"),
            "address": chef.get("address"),
        },
        "count": len(food_items),
        "items": grouped_items
    }


#----------------------------------------------create review ----------------------------------------#
@router.post("/chef/review")
async def add_review(
    review: ReviewCreate,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["_id"]

    review_doc = {
        "user_id": ObjectId(user_id),
        "chef_id": ObjectId(review.chef_id),
        "taste_rating": review.taste_rating,
        "portion_rating": review.portion_rating,
        "review_text": review.review_text,
        "created_at": datetime.utcnow()
    }

    result = await db["chef_reviews"].insert_one(review_doc)

    return {
        "status": "success",
        "review_id": str(result.inserted_id)
    }


#-----------------------------------------------------get review-----------------------------------#
@router.get("/chef/{chef_id}/reviews")
async def get_chef_reviews(chef_id: str):
    try:
        chef_obj_id = ObjectId(chef_id)
    except:
        return {"status": "error", "message": "Invalid chef_id"}

    reviews = await db["chef_reviews"].find(
        {"chef_id": chef_obj_id}
    ).sort("created_at", -1).to_list(length=None)

    # Convert ObjectId to string
    for r in reviews:
        r["_id"] = str(r["_id"])
        r["user_id"] = str(r["user_id"])
        r["chef_id"] = str(r["chef_id"])
        r["created_at"] = r["created_at"].isoformat()

    # ✅ Optional: calculate average ratings
    if reviews:
        avg_taste = sum(r["taste_rating"] for r in reviews) / len(reviews)
        avg_portion = sum(r["portion_rating"] for r in reviews) / len(reviews)
    else:
        avg_taste = avg_portion = 0

    return {
        "status": "success",
        "count": len(reviews),
        "average_ratings": {
            "taste": round(avg_taste, 1),
            "portion": round(avg_portion, 1)
        },
        "reviews": reviews
    }





#---------------------------------------------------About chef----------------------------------#

@router.get("/chef/about/{chef_id}")
async def get_chef_about(chef_id: str):
    try:
        chef_obj_id = ObjectId(chef_id)
    except:
        return {"status": "error", "message": "Invalid chef_id"}

    # Find chef
    chef = await db["chef_user"].find_one({"_id": chef_obj_id})
    if not chef:
        return {"status": "error", "message": "Chef not found"}

    # ✅ Extract bio (about)
    about_data = chef.get("profile", {}).get("bio")

    return {
        "status": "success",
        "chef_id": str(chef["_id"]),
        "about": about_data
    }

#--------------------------------------------------all fod of particulat chef-------------------------------#
@router.get("/food/by-chef/{chef_id}")
async def get_food_by_chef(chef_id: str):
    try:
        chef_obj_id = ObjectId(chef_id)
    except:
        return {"status": "error", "message": "Invalid chef_id"}

    # 1️⃣ Check if chef exists
    chef = await db["chef_user"].find_one({"_id": chef_obj_id})
    if not chef:
        return {"status": "error", "message": "Chef not found"}

    # 2️⃣ Get food items for that chef
    food_items = await db["food_items"].find({
        "chef_id": chef_obj_id
    }).to_list(length=None)

    # Convert ObjectId to string
    for item in food_items:
        item["_id"] = str(item["_id"])
        item["chef_id"] = str(item["chef_id"])

    # 3️⃣ Group by service_type
    grouped_items = {
        "Breakfast": [],
        "Lunch": [],
        "Dinner": []
    }
    for item in food_items:
        stype = item.get("service_type", "Others").capitalize()
        if stype in grouped_items:
            grouped_items[stype].append(item)
        else:
            # If unexpected service_type comes, put under "Others"
            if "Others" not in grouped_items:
                grouped_items["Others"] = []
            grouped_items["Others"].append(item)

    return {
        "status": "success",
        "chef": {
            "_id": str(chef["_id"]),
            "name": chef.get("name"),
            "address": chef.get("address"),
        },
        "count": len(food_items),
        "items": grouped_items
    }





#--------------------------------------------------------USER CART-------------------------#
from fastapi.encoders import jsonable_encoder\

def convert_mongo_document(doc):
    """Recursively convert ObjectId and datetime to strings."""
    if isinstance(doc, dict):
        return {k: convert_mongo_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [convert_mongo_document(i) for i in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    return doc

@router.post("/cart/add")
async def add_to_cart(item: CartItemRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only app users can add to cart")
    
    user_id = str(current_user["_id"])

    food_item = await db["food_items"].find_one({"_id": ObjectId(item.food_id)})
    if not food_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    cart = await db["carts"].find_one({"user_id": user_id})
    if not cart:
        cart = {
            "user_id": user_id,
            "items": [],
            "total_price": 0,
            "last_update": datetime.utcnow()
        }

    # ✅ Always increase quantity by 1
    for cart_item in cart["items"]:
        if cart_item["food_id"] == str(food_item["_id"]):
            cart_item["quantity"] += 1
            break
    else:
        cart["items"].append({
            "food_id": str(food_item["_id"]),
            "chef_id": str(food_item["chef_id"]),
            "food_name": food_item["food_name"],
            "quantity": 1,  # start at 1
            "price": food_item["price"],
            "photo_url":food_item["photo_url"]
        })

    cart["total_price"] = sum(i["price"] * i["quantity"] for i in cart["items"])
    cart["last_update"] = datetime.utcnow()

    await db["carts"].update_one(
        {"user_id": user_id},
        {"$set": cart},
        upsert=True
    )

    saved_cart = await db["carts"].find_one({"user_id": user_id})
    return {"status": "success", "cart": convert_mongo_document(saved_cart)}


#-------------------------------remove cart----------------------#
@router.post("/cart/remove")
async def remove_from_cart(item: CartItemRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only app users can remove from cart")
    
    user_id = str(current_user["_id"])

    cart = await db["carts"].find_one({"user_id": user_id})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=404, detail="Cart is empty")

    updated_items = []
    item_removed = False

    for cart_item in cart["items"]:
        if cart_item["food_id"] == item.food_id:
            # ✅ Always decrease by 1
            if cart_item["quantity"] > 1:
                cart_item["quantity"] -= 1
                updated_items.append(cart_item)
            else:
                item_removed = True
                continue
        else:
            updated_items.append(cart_item)

    if not updated_items and not item_removed:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    cart["items"] = updated_items
    cart["total_price"] = sum(i["price"] * i["quantity"] for i in cart["items"])
    cart["last_update"] = datetime.utcnow()

    if not cart["items"]:
        await db["carts"].delete_one({"user_id": user_id})
        return {"status": "success", "message": "Cart is now empty"}

    await db["carts"].update_one(
        {"user_id": user_id},
        {"$set": cart},
        upsert=True
    )

    saved_cart = await db["carts"].find_one({"user_id": user_id})
    return {"status": "success", "cart": convert_mongo_document(saved_cart)}


#---------------------------------------------------get cart item-------------------------------#
@router.get("/cart/me")
async def get_my_cart(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])  # ensure string

    # ✅ Query with string user_id (not ObjectId)
    cart = await db["carts"].find_one({"user_id": user_id})
    if not cart:
        return {"status": "success", "cart": []}

    # ✅ Convert ObjectIds to strings
    cart["_id"] = str(cart["_id"])
    cart["user_id"] = str(cart["user_id"])
    for item in cart.get("items", []):
        if "food_id" in item:
            item["food_id"] = str(item["food_id"])

    return {"status": "success", "cart": cart}


#-----------------------------------------Address---------------------------------------#
# -------------------
# Add a new address
# -------------------
@router.post("/user/address")
async def add_address(address: Address, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    address.user_id = user_id

    # If this address is default, unset other default addresses
    if address.is_default:
        await db["addresses"].update_many(
            {"user_id": user_id, "is_default": True},
            {"$set": {"is_default": False}}
        )

    address_dict = address.dict()
    address_dict["id"] = str(uuid.uuid4())
    result = await db["addresses"].insert_one(address_dict)
    address_dict["_id"] = str(result.inserted_id)

    return {"status": "success", "address": address_dict}

# -------------------
# Get all addresses
# -------------------
@router.get("/user/address")
async def get_addresses(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    addresses = await db["addresses"].find({"user_id": user_id}).to_list(100)

    # Convert MongoDB ObjectId to string
    for addr in addresses:
        addr["_id"] = str(addr["_id"])

    return {"addresses": addresses}

# -------------------
# Update address
# -------------------
@router.put("/user/address/{address_id}")
async def update_address(address_id: str, address: Address, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    
    # If setting this address as default, unset others
    if address.is_default:
        await db["addresses"].update_many(
            {"user_id": user_id, "is_default": True},
            {"$set": {"is_default": False}}
        )

    update_result = await db["addresses"].update_one(
        {"id": address_id, "user_id": user_id},
        {"$set": address.dict(exclude={"user_id"})}
    )

    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Address not found")

    return {"status": "success"}

# -------------------
# Delete address
# -------------------
@router.delete("/user/address/{address_id}")
async def delete_address(address_id: str, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    delete_result = await db["addresses"].delete_one({"id": address_id, "user_id": user_id})

    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Address not found")

    return {"status": "success"}


#-----------------------------------------Create Order------------------------------------#

@router.post("/orders/create")
async def create_order(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only users can create orders")

    user_id = str(current_user["_id"])

    # Fetch user's cart
    cart = await db["carts"].find_one({"user_id": user_id})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Fetch the default address
    address = await db["addresses"].find_one({"user_id": user_id, "is_default": True})
    if not address:
        raise HTTPException(status_code=404, detail="No default address found")

    # Convert ObjectId to string
    address["_id"] = str(address["_id"])

    chef_id = cart["items"][0]["chef_id"]  # assume same chef for all items

    # Create new order
    order = {
        "user_id": user_id,
        "chef_id": chef_id,
        "items": cart["items"],
        "total_price": cart["total_price"],
        "address": address,          # include the default address
        "status": "pending",
        "chef_status": "pending",
        "delivery_status": "pending",
        "created_at": datetime.utcnow()
    }

    result = await db["orders"].insert_one(order)
    order["_id"] = str(result.inserted_id)

    # Clear the cart
    await db["carts"].delete_one({"user_id": user_id})

    return {
        "status": "success",
        "message": "Order created successfully",
        "order": order
    }


@router.get("/orders/user")
async def get_user_orders(current_user: dict = Depends(get_current_user)):
    """Get all orders placed by the user."""
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only users can view their orders")

    user_id = str(current_user["_id"])
    orders_cursor = db["orders"].find({"user_id": user_id}).sort("created_at", -1)

    orders = []
    async for order in orders_cursor:
        order["_id"] = str(order["_id"])
        if "address" in order and "_id" in order["address"]:
            order["address"]["_id"] = str(order["address"]["_id"])
        orders.append(order)

    return {"status": "success", "orders": orders}

#-------------------------------get individual order--------------------------#

@router.get("/orders/user/{order_id}")
async def get_user_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific order placed by the user."""
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only users can view this")

    try:
        oid = ObjectId(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db["orders"].find_one({"_id": oid, "user_id": str(current_user["_id"])})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order["_id"] = str(order["_id"])
    if "address" in order and "_id" in order["address"]:
        order["address"]["_id"] = str(order["address"]["_id"])

    return {"status": "success", "order": order}



from pydantic import BaseModel
class ChefResponseRequest(BaseModel):
    order_id: str
    response: str  # "accept" or "reject"

@router.post("/orders/chef/response")
async def chef_response(payload: ChefResponseRequest, current_user: dict = Depends(get_current_user)):
    # Check if the user is a chef
    if current_user["role"] != "chef":
        raise HTTPException(status_code=403, detail="Only chefs can respond")

    chef_id = str(current_user["_id"])
    order_id = payload.order_id
    response = payload.response.lower()

    # Fetch the order
    order = await db["orders"].find_one({"_id": ObjectId(order_id)})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order["chef_id"]) != chef_id:
        raise HTTPException(status_code=403, detail="This order does not belong to you")
    if order["chef_status"] != "pending":
        raise HTTPException(status_code=400, detail="Order has already been processed")
    if response not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid response, must be 'accept' or 'reject'")

    # Update chef_status and overall status
    chef_status = "accepted" if response == "accept" else "rejected"
    status = "chef_accepted" if chef_status == "accepted" else "cancelled"

    await db["orders"].update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"chef_status": chef_status, "status": status}}
    )

    # Assign delivery boy if chef accepted
    if chef_status == "accepted":
        chef_obj = await db["chef_user"].find_one({"_id": ObjectId(chef_id)})
        if chef_obj and chef_obj.get("location"):
            # Set delivery_status to pending_assignment
            await db["orders"].update_one(
                {"_id": ObjectId(order_id)},
                {"$set": {"delivery_status": "pending_assignment"}}
            )
            # Fire-and-forget async assignment to nearby delivery boys
            asyncio.create_task(assign_order(order_id, chef_obj["location"]))

    return {
        "status": "success",
        "message": f"Order {response}ed successfully",
        "order_id": order_id,
        "chef_status": chef_status
    }
import math

# Active WebSocket connections (delivery_boy_id: websocket)
active_connections = {}
# Shared responses (order_id -> delivery_boy_id -> response)
delivery_responses = {}  # Example: {"order123": {"boy1": "accept", "event": asyncio.Event()}}

# MongoDB collections
delivery_user = db["delivery_user"]
orders_collection = db["orders"]


# ------------------------------
# Haversine Distance Function
# ------------------------------
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # distance in meters


# ------------------------------
# Find Nearby Delivery Boys
# ------------------------------
async def find_nearby_delivery_boys(chef_location: dict, max_distance: int = 5000):
    chef_lon, chef_lat = chef_location["coordinates"]

    delivery_boys_cursor = db["delivery_user"].find({
        "role": "delivery",
        "status": True,  # must be online
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [chef_lon, chef_lat]},
                "$maxDistance": max_distance
            }
        }
    })

    nearby_delivery_boys = []
    async for delivery_boy in delivery_boys_cursor:
        boy_lon, boy_lat = delivery_boy["location"]["coordinates"]
        distance = haversine(chef_lon, chef_lat, boy_lon, boy_lat)

        nearby_delivery_boys.append({
            "id": str(delivery_boy["_id"]),
            "name": delivery_boy.get("name"),
            "location": delivery_boy.get("location"),
            "distance_meters": round(distance, 2)
        })

    return nearby_delivery_boys

# ------------------------------
# Assign Order with Retry
# ------------------------------
async def assign_order(order_id: str, chef_location: dict, max_distance: int = 5000, timeout: int = 30):
    nearby_delivery_boys = await find_nearby_delivery_boys(chef_location, max_distance)

    if not nearby_delivery_boys:
        print(f"[DEBUG] No delivery boys available for order {order_id}")
        return

    if order_id not in delivery_responses:
        delivery_responses[order_id] = {"event": asyncio.Event()}

    for boy in nearby_delivery_boys:
        delivery_boy_id = boy["id"]
        if delivery_boy_id not in active_connections:
            continue  # skip offline

        ws = active_connections[delivery_boy_id]

        # Send order request
        await ws.send_json({
            "type": "order_request",
            "order_id": order_id,
            "message": "New delivery request assigned to you!"
        })
        print(f"[DEBUG] Sent order request to {delivery_boy_id}")

        try:
            # Wait until delivery boy responds or timeout
            delivery_responses[order_id]["event"].clear()
            try:
                await asyncio.wait_for(delivery_responses[order_id]["event"].wait(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"[DEBUG] Delivery boy {delivery_boy_id} did not respond in {timeout}s")
                continue  # try next nearby delivery boy

            # Check response
            response = delivery_responses[order_id].get(delivery_boy_id)
            if response == "accept":
                await orders_collection.update_one(
                    {"_id": ObjectId(order_id)},
                    {"$set": {
                        "delivery_boy_id": delivery_boy_id,
                        "delivery_status": "assigned",
                        "accepted_at": datetime.utcnow()
                    }}
                )
                print(f"[DEBUG] Order {order_id} assigned to {delivery_boy_id}")
                await ws.send_json({"type": "order_status", "order_id": order_id, "status": "accepted"})
                return
            else:
                print(f"[DEBUG] Delivery boy {delivery_boy_id} rejected order {order_id}")
                continue  # next boy

        except WebSocketDisconnect:
            print(f"[DEBUG] Delivery boy {delivery_boy_id} disconnected")
            if delivery_boy_id in active_connections:
                del active_connections[delivery_boy_id]
            continue

    print(f"[DEBUG] No delivery boy accepted order {order_id}")
    await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"delivery_status": "unassigned"}}
    )

# ------------------------------
# Delivery Boy WebSocket
# ------------------------------
@router.websocket("/ws/delivery/{delivery_boy_id}")
async def delivery_boy_ws(websocket: WebSocket, delivery_boy_id: str):
    await websocket.accept()
    active_connections[delivery_boy_id] = websocket
    print(f"[DEBUG] Delivery boy {delivery_boy_id} connected")

    # Mark online in DB
    await delivery_user.update_one(
        {"_id": ObjectId(delivery_boy_id)},
        {"$set": {"status": True, "last_update": datetime.utcnow()}}
    )

    try:
        while True:
            data = await websocket.receive_json()
            print(f"[DEBUG] Received from {delivery_boy_id}: {data}")

            if data.get("type") == "order_response":
                order_id = data.get("order_id")
                response = data.get("response")  # "accept" or "reject"

                # Store response
                if order_id not in delivery_responses:
                    delivery_responses[order_id] = {"event": asyncio.Event()}

                delivery_responses[order_id][delivery_boy_id] = response
                # Notify the assign_order task
                delivery_responses[order_id]["event"].set()

                # Send confirmation back to delivery boy
                await websocket.send_json({
                    "type": "order_status",
                    "order_id": order_id,
                    "status": response
                })

    except WebSocketDisconnect:
        print(f"[DEBUG] Delivery boy {delivery_boy_id} disconnected")
        if delivery_boy_id in active_connections:
            del active_connections[delivery_boy_id]
        # Mark offline
        await delivery_user.update_one(
            {"_id": ObjectId(delivery_boy_id)},
            {"$set": {"status": False, "last_update": datetime.utcnow()}}
        )

food_styles = [
    "Andhra Style",
    "Arunachal Pradesh Style",
    "Assam Style",
    "Bihar Style",
    "Chattisgarh Style",
    "Delhi Style",
    "Goa Style",
    "Gujarat Style",
    "Haryana Style",
    "Himachal Pradesh Style",
    "Jammu Kashmir Style",
    "Jharkhand Style",
    "Karnataka Style",
    "Kerala Style",
    "Madhya Pradesh Style",
    "Maharastrian Style",
    "Meghalaya Style",
    "Mizoram Style",
    "Nagaland Style",
    "Orissa Style",
    "Punjabi Style",
    "Rajasthan Style",
    "Sikkim Style",
    "Tamilian Style",
    "Telangana Style",
    "Tripura Style",
    "Uttrakhand Style",
    "Uttar Pradesh Style",
    "West Bengal Style"
]


from typing import List

@router.get("/food-styles", response_model=List[str])
def get_food_styles():
    return food_styles
