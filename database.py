from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://13.204.84.41:27017")
db = client["maakitchen"]
