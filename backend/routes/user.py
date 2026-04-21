from fastapi import APIRouter, Header, HTTPException

from backend.db.database import users_collection
from backend.models.auth_models import ChangePasswordRequest, UserLogin, UserSignup
from backend.services.auth_service import (
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
    await users_collection.insert_one(user_document)

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
