from datetime import timedelta

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
from backend.services.service_helpers import ensure_unique_user_fields, now_utc, object_id_or_400, visible_filter
from backend.utils.responses import message_response


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
        "is_deleted": bool(user.get("is_deleted", False)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


def is_admin(current_user: dict) -> bool:
    return str(current_user.get("role", "")).strip().lower() in {
        UserRole.ADMIN.value,
        UserRole.SUPER_ADMIN.value,
    }


async def signup_user(payload: UserSignup) -> UserOut:
    users_collection = get_users_collection()
    await ensure_unique_user_fields(users_collection, email=payload.email, phone=payload.phone)

    hashed_password = hash_password(payload.password)
    timestamp = now_utc()
    user_document = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "hashed_password": hashed_password,
        "role": UserRole.USER.value,
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_active": True,
        "is_deleted": False,
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
    if not bool(user.get("is_active", True)) or bool(user.get("is_deleted", False)):
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
            "logged_in_at": now_utc(),
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
        {"$set": {"hashed_password": hash_password(payload.new_password), "updated_at": now_utc()}},
    )
    return message_response("Password changed successfully")


async def create_manual_user(payload: UserCreate) -> dict:
    users_collection = get_users_collection()
    await ensure_unique_user_fields(users_collection, email=payload.email, phone=payload.phone)

    timestamp = now_utc()
    user_document = {
        "name": payload.name,
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
        "role": UserRole.USER.value,
        "is_active": True,
        "is_deleted": False,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if payload.phone:
        user_document["phone"] = payload.phone
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
        visible_filter(),
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    ).to_list(length=1000)
    return [sanitize_user(user) for user in users]


async def get_visible_user(user_id: str, current_user: dict) -> dict:
    object_id = object_id_or_400(user_id)
    is_self = str(current_user.get("_id")) == user_id
    if not (is_self or is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user = await get_users_collection().find_one(
        {"_id": object_id},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if bool(user.get("is_deleted", False)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return sanitize_user(user)


async def update_visible_user(user_id: str, payload: UserUpdate) -> dict:
    object_id = object_id_or_400(user_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updates["updated_at"] = now_utc()

    users_collection = get_users_collection()
    await ensure_unique_user_fields(
        users_collection,
        email=updates.get("email"),
        phone=updates.get("phone"),
        exclude_id=object_id,
    )

    result = await users_collection.update_one(visible_filter({"_id": object_id}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user = await users_collection.find_one(
        {"_id": object_id},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return sanitize_user(user)


async def delete_visible_user(user_id: str) -> None:
    object_id = object_id_or_400(user_id)
    result = await get_users_collection().update_one(
        visible_filter({"_id": object_id}),
        {"$set": {"is_deleted": True, "is_active": False, "deleted_at": now_utc()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
