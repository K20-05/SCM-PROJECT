from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

from backend.config.app_config import settings
from backend.database.mongo import get_logins_collection, get_users_collection
from backend.models.user_model import ChangePasswordRequest, UserLogin, UserSignup
from backend.auth import (
    admin_required,
    create_access_token,
    generate_password_hash,
    get_current_user,
    get_user_by_email,
    get_user_data,
    role_exists,
    super_admin_required,
    verify_password,
)


router = APIRouter(prefix="/user", tags=["User"])


@router.post("/signup")
async def signup(user: UserSignup):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    assigned_role = settings.default_role
    if not role_exists(assigned_role):
        raise HTTPException(status_code=400, detail="Invalid role")

    user_document = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "password_hash": generate_password_hash(user.password),
        "role": assigned_role,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        await get_users_collection().insert_one(user_document)
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

    await get_logins_collection().insert_one(
        {
            "email": stored_user["email"],
            "role": stored_user.get("role", settings.default_role),
            "logged_in_at": datetime.now(timezone.utc),
        }
    )

    return {
        "message": "Login successful",
        "token_type": "bearer",
        "access_token": create_access_token(str(stored_user["_id"])),
        "user": get_user_data(stored_user),
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    current_hash = current_user.get("password_hash", "")
    if not current_hash or not verify_password(payload.old_password, current_hash):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    new_hash = generate_password_hash(payload.new_password)
    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {"$set": {"password_hash": new_hash}},
    )
    return {"message": "Password changed successfully"}


@router.get("/admin-only")
async def admin_only(_current_user: dict = Depends(admin_required)):
    return {"message": "Admin access granted"}


@router.get("/super-admin-only")
async def super_admin_only(_current_user: dict = Depends(super_admin_required)):
    return {"message": "Super admin access granted"}
