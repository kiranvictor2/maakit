# routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from auth.jwt_handler import get_current_user
from models.user import FoodFilter   # adjust path to your actual file
from database import get_db
from models.user import UserCreate
from database import db
from models.user import LoginRequest,userPhoneCreate,LocationUpdate,ReviewCreate
from auth.utils import create_access_token  # ✅ Import token creator
from datetime import datetime

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




@router.post("/userlocation/update")
async def update_location(
    location: LocationUpdate, 
    current_user: dict = Depends(get_current_user)
):
    # safer: use sub instead of _id
    user_id = current_user.get("sub")  

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
    user_id = current_user["sub"]

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
    user_id = current_user["sub"]

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
    user_id = current_user["sub"]

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


food_styles = [
    "Andhra", "Telangana", "Karnataka", "Maharashtrian", "Tamil Nadu",
    "Kerala", "Bengali", "Punjabi", "Rajasthani", "Gujarati", "Goan",
    "Kashmiri", "Odia", "Assamese", "Sikkimese", "Naga", "Manipuri",
    "Mizo", "Tripuri", "Arunachali", "Meghalayan", "Madhya Pradesh",
    "Chhattisgarhi"
]

from typing import List

@router.get("/food-styles", response_model=List[str])
def get_food_styles():
    return food_styles