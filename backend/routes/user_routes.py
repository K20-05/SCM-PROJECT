from fastapi import APIRouter, Header, HTTPException
from pymongo.errors import DuplicateKeyError
import os
from datetime import datetime, timezone

from backend.database.mongo import logins_collection, users_collection
from backend.models.user_model import ChangePasswordRequest, UserLogin, UserSignup
from backend.auth import (
    create_access_token,
    decode_access_token,
    extract_bearer_token,
    generate_password_hash,
    get_user_by_email,
    get_user_data,
    verify_password,
)


router = APIRouter(prefix="/user", tags=["User"])


@router.post("/signup")
async def signup(user: UserSignup):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user_document = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "password_hash": generate_password_hash(user.password),
    }
    try:
        await users_collection.insert_one(user_document)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="User already exists") from None

    return {
        "message": "User registered successfully",
        "user": get_user_data(user_document),
    }


@router.post("/login")
async def login(user: UserLogin):
    stored_user = await get_user_by_email(user.email)
    if not stored_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_hash = stored_user.get("password_hash", "")
    if not password_hash or not verify_password(user.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await logins_collection.insert_one(
        {
            "email": stored_user["email"],
            "logged_in_at": datetime.now(timezone.utc),
        }
    )

    return {
        "message": "Login successful",
        "token_type": "bearer",
        "access_token": create_access_token(stored_user["email"]),
        "user": get_user_data(stored_user),
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    authorization: str | None = Header(default=None),
):
    token = extract_bearer_token(authorization)
    token_payload = decode_access_token(token)
    user_email = token_payload.get("sub")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    stored_user = await get_user_by_email(user_email)
    if not stored_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_hash = stored_user.get("password_hash", "")
    if not current_hash or not verify_password(payload.old_password, current_hash):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    new_hash = generate_password_hash(payload.new_password)
    await users_collection.update_one(
        {"email": user_email},
        {"$set": {"password_hash": new_hash}},
    )
    return {"message": "Password changed successfully"}


@router.get("/debug/users")
async def debug_users():
    if os.getenv("DEBUG_ROUTES_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    users = await users_collection.find(
        {},
        {"_id": 0, "email": 1, "password_hash": 1, "password": 1},
    ).to_list(length=1000)

    return {
        "count": len(users),
        "users": [
            {
                "email": user.get("email"),
                "has_password_hash": bool(user.get("password_hash")),
                "has_plain_password": bool(user.get("password")),
            }
            for user in users
        ],
    }


@router.delete("/debug/cleanup-plain-password-users")
async def cleanup_plain_password_users():
    if os.getenv("DEBUG_ROUTES_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    result = await users_collection.delete_many(
        {
            "password": {"$exists": True},
            "$or": [
                {"password_hash": {"$exists": False}},
                {"password_hash": ""},
                {"password_hash": None},
            ],
        }
    )
    return {"deleted_count": result.deleted_count}
