from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from auth.access_control import require_role
from auth.auth_config import settings as auth_settings
from auth.auth_deps import get_current_user
from auth.auth_utils import create_access_token, hash_password, verify_password
from backend.database.mongo import get_logins_collection, get_users_collection
from backend.models.auth_models import ChangePasswordRequest, Token, UserCreate, UserLogin, UserOut, UserRole, UserSignup, UserUpdate


router = APIRouter(prefix="/api/auth", tags=["Auth"])
user_crud_router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignup):
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
        "password_hash": hashed_password,
        "role": UserRole.USER.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_active": True,
    }

    try:
        await users_collection.insert_one(user_document)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered") from None

    return UserOut(
        name=user_document["name"],
        email=user_document["email"],
        phone=user_document["phone"],
        role=user_document["role"],
    )


@router.post("/login", response_model=Token)
async def login(request: Request):
    users_collection = get_users_collection()
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    content_type = (request.headers.get("content-type") or "").lower()
    email = ""
    password = ""

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        # Swagger OAuth2 password flow sends username/password.
        email = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
    else:
        data = await request.json()
        payload = UserLogin.model_validate(data)
        email = payload.email
        password = payload.password

    user = await users_collection.find_one({"email": email})
    if not user:
        raise invalid_credentials_error

    hashed_password = user.get("hashed_password", "")
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

    access_token = create_access_token(
        data={
            "sub": str(user["_id"]),
            "role": user.get("role", UserRole.USER.value),
        },
        expires_delta=timedelta(minutes=auth_settings.jwt_expire_minutes),
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserOut(
        name=current_user.get("name", ""),
        email=current_user.get("email", ""),
        phone=current_user.get("phone", ""),
        role=current_user.get("role", UserRole.USER.value),
    )


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    existing_hash = current_user.get("hashed_password") or current_user.get("password_hash")
    if not existing_hash or not verify_password(payload.old_password, existing_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Old password is incorrect")

    new_hash = hash_password(payload.new_password)
    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                # Keep both keys for backward compatibility with legacy /user routes.
                "hashed_password": new_hash,
                "password_hash": new_hash,
            }
        },
    )
    return {"message": "Password changed successfully"}


@router.post("/refresh", response_model=Token)
async def refresh_access_token(current_user: dict = Depends(get_current_user)):
    access_token = create_access_token(
        data={
            "sub": str(current_user["_id"]),
            "role": current_user.get("role", UserRole.USER.value),
        },
        expires_delta=timedelta(minutes=auth_settings.jwt_expire_minutes),
    )
    return Token(access_token=access_token, token_type="bearer")


@user_crud_router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate):
    users_collection = get_users_collection()
    existing_user = await users_collection.find_one({"email": payload.email})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    hashed_password = hash_password(payload.password)
    user_document = {
        "name": payload.name,
        "email": payload.email,
        "hashed_password": hashed_password,
        "password_hash": hashed_password,
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


def _is_admin(current_user: dict) -> bool:
    return str(current_user.get("role", "")).strip().lower() in {
        UserRole.ADMIN.value,
        UserRole.SUPER_ADMIN.value,
    }


def _sanitize_user(user: dict) -> dict:
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


@user_crud_router.get("", dependencies=[Depends(require_role("admin"))])
async def list_users():
    users = await get_users_collection().find(
        {},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    ).to_list(length=1000)
    return [_sanitize_user(user) for user in users]


@user_crud_router.get("/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    is_self = str(current_user.get("_id")) == user_id
    if not (is_self or _is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user = await get_users_collection().find_one(
        {"_id": ObjectId(user_id)},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return _sanitize_user(user)


@user_crud_router.put("/me")
async def update_me(payload: UserUpdate, current_user: dict = Depends(get_current_user)):
    return await update_user(str(current_user["_id"]), payload, current_user)


@user_crud_router.put("/{user_id}", dependencies=[Depends(require_role("admin"))], include_in_schema=False)
async def update_user(user_id: str, payload: UserUpdate, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)

    users_collection = get_users_collection()
    if "email" in updates:
        existing = await users_collection.find_one({"email": updates["email"], "_id": {"$ne": ObjectId(user_id)}})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    user = await users_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"password": 0, "password_hash": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _sanitize_user(user)


@user_crud_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role("admin"))])
async def delete_user(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    result = await get_users_collection().delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return None
