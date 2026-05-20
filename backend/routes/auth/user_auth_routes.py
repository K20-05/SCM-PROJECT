from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from auth.auth_config import settings as auth_settings
from auth.auth_deps import get_current_user
from auth.auth_utils import create_access_token, hash_password, verify_password
from backend.database.mongo import get_users_collection
from backend.models.auth_models import Token, UserCreate, UserLogin, UserOut, UserRole, UserSignup


router = APIRouter(prefix="/api/auth", tags=["Auth"])
user_crud_router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignup):
    users_collection = get_users_collection()

    existing_user = await users_collection.find_one({"email": payload.email})
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_document = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "hashed_password": hash_password(payload.password),
        "role": UserRole.CUSTOMER.value,
        "created_at": datetime.now(timezone.utc),
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
async def login(payload: UserLogin):
    users_collection = get_users_collection()
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    user = await users_collection.find_one({"email": payload.email})
    if not user:
        raise invalid_credentials_error

    hashed_password = user.get("hashed_password", "")
    if not hashed_password or not verify_password(payload.password, hashed_password):
        raise invalid_credentials_error

    access_token = create_access_token(
        data={
            "sub": str(user["_id"]),
            "role": user.get("role", UserRole.CUSTOMER.value),
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
        role=current_user.get("role", UserRole.CUSTOMER.value),
    )


@user_crud_router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate):
    users_collection = get_users_collection()
    existing_user = await users_collection.find_one({"email": payload.email})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_document = {
        "name": payload.name,
        "email": payload.email,
        "password": payload.password,
        "created_at": datetime.now(timezone.utc),
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


@user_crud_router.get("/{user_id}")
async def get_user(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    user = await get_users_collection().find_one(
        {"_id": ObjectId(user_id)},
        {"_id": 0, "password": 0, "hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user
