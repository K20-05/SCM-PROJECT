import bcrypt
from fastapi import APIRouter, HTTPException

from backend.db.database import users_collection
from backend.models.auth_models import UserLogin, UserSignup


router = APIRouter(prefix="/user", tags=["User"])


@router.post("/signup")
async def signup(user: UserSignup):
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    password_hash = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user_document = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "password_hash": password_hash,
    }
    await users_collection.insert_one(user_document)

    return {
        "message": "User registered successfully",
        "user": {
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
        },
    }


@router.post("/login")
async def login(user: UserLogin):
    stored_user = await users_collection.find_one({"email": user.email})
    if not stored_user:
        # Avoid ambiguous "404 Not Found" responses for valid login route hits.
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_hash = stored_user.get("password_hash", "")
    if not password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        password_ok = bcrypt.checkpw(user.password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials") from None
    if not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Login successful",
        "user": {
            "name": stored_user["name"],
            "email": stored_user["email"],
            "phone": stored_user["phone"],
        },
    }
