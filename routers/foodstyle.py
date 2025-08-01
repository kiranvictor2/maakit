from fastapi import APIRouter, Depends
from models.foodstyle import FoodStyle
from database import db
from auth.jwt_handler import get_current_user  # ✅ 

router = APIRouter(
    dependencies=[Depends(get_current_user)]  # ✅ this makes all routes below protected
)

@router.post("/food-styles")
async def create_food_style(style: FoodStyle):
    existing = await db["food_styles"].find_one({"name": style.name})
    if existing:
        return {"message": "Already exists", "id": str(existing["_id"])}

    result = await db["food_styles"].insert_one(style.dict())
    return {"message": "Created", "id": str(result.inserted_id)}

@router.get("/food-styles")
async def get_all_food_styles(current_user: dict = Depends(get_current_user)):
    username = current_user.get("phone_number")
    print(username)
    styles = await db["food_styles"].find().to_list(100)
    return {
        "styles": [{"id": str(s["_id"]), "name": s["name"]} for s in styles]
    }

# @router.post("/insert-defaults")
# async def insert_default_food_styles():
#     styles = [
#         "Andhra", "Telangana", "Karnataka", "Maharashtrian", "Tamil Nadu", "Kerala", "Bengali",
#         "Punjabi", "Rajasthani", "Gujarati", "Goan", "Kashmiri", "Odia", "Assamese", "Sikkimese",
#         "Naga", "Manipuri", "Mizo", "Tripuri", "Arunachali", "Meghalayan", "Madhya Pradesh", "Chhattisgarhi"
#     ]

#     inserted = 0
#     for name in styles:
#         existing = await db["food_styles"].find_one({"name": name})
#         if not existing:
#             await db["food_styles"].insert_one({"name": name})
#             inserted += 1

#     return {"message": f"{inserted} food styles inserted"}
