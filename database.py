from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://3.110.207.229:27017")
db = client["maakitchen"]

async def get_db():
    return db