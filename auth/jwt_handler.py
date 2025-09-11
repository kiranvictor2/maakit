# from fastapi import Depends, HTTPException
# from fastapi.security import OAuth2PasswordBearer
# from jose import jwt, JWTError

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# SECRET_KEY = "your-super-secret-key"
# ALGORITHM = "HS256"

# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         if not user_id:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return payload
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")


from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from database import db
from bson import ObjectId

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = "your-super-secret-key"
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")

        if not user_id or not role:
            raise HTTPException(status_code=401, detail="Invalid token")

        # pick correct collection
        if role == "user":
            collection = "app_user"
        elif role == "chef":
            collection = "chef_user"
        elif role == "delivery":
            collection = "delivery_user"
        else:
            raise HTTPException(status_code=401, detail="Unknown role")

        user = await db[collection].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user["role"] = role  # attach role to response
        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
