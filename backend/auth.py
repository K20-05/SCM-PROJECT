from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from auth.auth_utils import hash_password, verify_password as verify_password_hash
from backend.config.app_config import (
    settings,
    load_role_seed_data,
)
from backend.database.mongo import get_users_collection


if settings.jwt_secret in {"change-me-in-env", "change-this-to-a-strong-random-secret"}:
    raise RuntimeError("Set a strong JWT_SECRET_KEY in .env before starting the app")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")
ROLE_LEVELS = {role["name"]: role["level"] for role in load_role_seed_data()}


def generate_password_hash(password: str) -> str:
    return hash_password(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return verify_password_hash(plain_password, password_hash)
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, str | int] = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_user_by_email(email: str) -> dict | None:
    return await get_users_collection().find_one({"email": email})


async def get_user_by_id(user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await get_users_collection().find_one({"_id": ObjectId(user_id)})


def get_role_level(role_name: str) -> int | None:
    normalized = role_name.strip().lower()
    return ROLE_LEVELS.get(normalized)


def role_exists(role_name: str) -> bool:
    return get_role_level(role_name) is not None


def get_user_data(user_document: dict) -> dict:
    return {
        "name": user_document["name"],
        "email": user_document["email"],
        "phone": user_document["phone"],
        "role": user_document.get("role", "user"),
    }


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if not ObjectId.is_valid(user_id):
        raise credentials_exception
    user = await get_users_collection().find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def admin_required(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def super_admin_required(user: dict = Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return user
