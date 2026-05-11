from datetime import datetime, timedelta, timezone

import bcrypt
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from backend.config.app_config import (
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
    load_role_seed_data,
)
from backend.database.mongo import users_collection


if JWT_SECRET_KEY in {"change-me-in-env", "change-this-to-a-strong-random-secret"}:
    raise RuntimeError("Set a strong JWT_SECRET_KEY in .env before starting the app")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")


def generate_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, str | int] = {
        "sub": user_email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return token


async def get_user_by_email(email: str) -> dict | None:
    return await users_collection.find_one({"email": email})


async def get_user_by_id(user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await users_collection.find_one({"_id": ObjectId(user_id)})


def _role_levels() -> dict[str, int]:
    return {role["name"]: role["level"] for role in load_role_seed_data()}


async def get_role_by_name(role_name: str) -> dict | None:
    levels = _role_levels()
    normalized = role_name.strip().lower()
    if normalized not in levels:
        return None
    return {"name": normalized, "level": levels[normalized]}


async def role_exists(role_name: str) -> bool:
    role = await get_role_by_name(role_name)
    return role is not None


def get_user_data(user_document: dict) -> dict:
    return {
        "name": user_document["name"],
        "email": user_document["email"],
        "phone": user_document["phone"],
        "role": user_document.get("role", "user"),
    }


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_email = payload.get("sub")
        if not user_email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await users_collection.find_one({"email": user_email})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def require_role(required_role_name: str):
    async def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        user_role_name = current_user.get("role")
        if not user_role_name:
            raise HTTPException(status_code=403, detail="User role not assigned")

        user_role = await get_role_by_name(user_role_name)
        required_role = await get_role_by_name(required_role_name)
        if not user_role or not required_role:
            raise HTTPException(status_code=403, detail="Role configuration not found")

        if user_role.get("level", 0) < required_role.get("level", 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        return current_user

    return role_dependency
