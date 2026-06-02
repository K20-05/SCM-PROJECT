from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def object_id_or_400(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")
    return ObjectId(value)


def visible_filter(extra: dict | None = None) -> dict:
    query = {"is_deleted": {"$ne": True}}
    if extra:
        query.update(extra)
    return query


async def ensure_unique_user_fields(users_collection, *, email: str | None = None, phone: str | None = None, exclude_id=None) -> None:
    exclusion = {"_id": {"$ne": exclude_id}} if exclude_id is not None else {}
    if email:
        existing = await users_collection.find_one({"email": email, **exclusion})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if phone:
        existing = await users_collection.find_one({"phone": phone, **exclusion})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")
