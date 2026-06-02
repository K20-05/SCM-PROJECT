from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from auth.auth_config import settings as auth_settings
from auth.auth_utils import create_access_token, hash_password, verify_password
from backend.database.mongo import get_logins_collection, get_users_collection
from backend.models.auth_models import (
    ChangePasswordRequest,
    Token,
    UserCreate,
    UserOut,
    UserRole,
    UserSignup,
    UserUpdate,
)


DASHBOARD_URLS = {
    UserRole.USER.value: "/dashboard/user",
    UserRole.ADMIN.value: "/dashboard/admin",
    UserRole.SUPER_ADMIN.value: "/dashboard/super-admin",
}


def token_for_user(user: dict) -> Token:
    role = user.get("role", UserRole.USER.value)
    access_token = create_access_token(
        data={
            "sub": str(user["_id"]),
            "role": role,
        },
        expires_delta=timedelta(minutes=auth_settings.jwt_expire_minutes),
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=role,
        dashboard_url=DASHBOARD_URLS.get(role, DASHBOARD_URLS[UserRole.USER.value]),
    )


def user_out_from_document(user: dict) -> UserOut:
    return UserOut(
        name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        role=user.get("role", UserRole.USER.value),
    )


def sanitize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "role": user.get("role", UserRole.USER.value),
        "is_active": bool(user.get("is_active", True)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


def is_admin(current_user: dict) -> bool:
    return str(current_user.get("role", "")).strip().lower() in {
        UserRole.ADMIN.value,
        UserRole.SUPER_ADMIN.value,
    }


def _object_id_or_400(user_id: str) -> ObjectId:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")
    return ObjectId(user_id)


async def signup_user(payload: UserSignup) -> UserOut:
    users_collection = get_users_collection()
    existing_user = await users_collection.find_one({"email": payload.email})
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_password = hash_password(payload.password)
    user_document = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "hashed_password": hashed_password,
        "role": UserRole.USER.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_active": True,
    }

    try:
        await users_collection.insert_one(user_document)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered") from None

    return user_out_from_document(user_document)


async def login_user(email: str, password: str) -> Token:
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )
    user = await get_users_collection().find_one({"email": email})
    if not user:
        raise invalid_credentials_error
    if not bool(user.get("is_active", True)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    hashed_password = user.get("hashed_password") or user.get("password_hash", "")
    if not hashed_password or not verify_password(password, hashed_password):
        raise invalid_credentials_error

    await get_logins_collection().insert_one(
        {
            "user_id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user["email"],
            "role": user.get("role", UserRole.USER.value),
            "logged_in_at": datetime.now(timezone.utc),
            "login_source": "frontend",
        }
    )
    return token_for_user(user)


async def change_user_password(payload: ChangePasswordRequest, current_user: dict) -> dict:
    existing_hash = current_user.get("hashed_password") or current_user.get("password_hash")
    if not existing_hash or not verify_password(payload.old_password, existing_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Old password is incorrect")

    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {"$set": {"hashed_password": hash_password(payload.new_password)}},
    )
    return {"message": "Password changed successfully"}


async def create_manual_user(payload: UserCreate) -> dict:
    users_collection = get_users_collection()
    existing_user = await users_collection.find_one({"email": payload.email})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_document = {
        "name": payload.name,
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
        "role": UserRole.USER.value,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        result = await users_collection.insert_one(user_document)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None

    return {
        "id": str(result.inserted_id),
        "name": user_document["name"],
        "email": user_document["email"],
        "created_at": user_document["created_at"],
    }


async def list_users_for_admin() -> list[dict]:
    users = await get_users_collection().find(
        {},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    ).to_list(length=1000)
    return [sanitize_user(user) for user in users]


async def get_visible_user(user_id: str, current_user: dict) -> dict:
    object_id = _object_id_or_400(user_id)
    is_self = str(current_user.get("_id")) == user_id
    if not (is_self or is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user = await get_users_collection().find_one(
        {"_id": object_id},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return sanitize_user(user)


async def update_visible_user(user_id: str, payload: UserUpdate) -> dict:
    object_id = _object_id_or_400(user_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)

    users_collection = get_users_collection()
    if "email" in updates:
        existing = await users_collection.find_one({"email": updates["email"], "_id": {"$ne": object_id}})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    await users_collection.update_one({"_id": object_id}, {"$set": updates})
    user = await users_collection.find_one(
        {"_id": object_id},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return sanitize_user(user)


async def delete_visible_user(user_id: str) -> None:
    object_id = _object_id_or_400(user_id)
    result = await get_users_collection().delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
