from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# Routers
from routers.user import router as user_router
from routers.chef import router as chef_router
from routers.foodstyle import router as food_style_router
from routers.delivery import router as delivery
from mongoengine import connect

app = FastAPI()
# Mount "uploads" folder
app.mount("/static", StaticFiles(directory="uploads"), name="static")
connect(db="maakitchen", host="mongodb://localhost:27017")
# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route registration
app.include_router(user_router, prefix="/api")
app.include_router(delivery, prefix="/api")
app.include_router(chef_router, prefix="/api")
app.include_router(food_style_router, prefix="/api")

# Health check (optional)
@app.get("/")
def read_root():
    return {"message": "API is up and running"}
