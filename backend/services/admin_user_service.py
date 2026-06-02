from bson import ObjectId
from fastapi import HTTPException, status

from backend.database.mongo import get_users_collection
from backend.models.auth_models import AdminUserOut, UserRole, UserRoleUpdate, UserStatusUpdate, UserUpdate


def normalize_role(value: str | None) -> UserRole:
    normalized = (value or "").strip().lower()
    if normalized == "customer":
        normalized = UserRole.USER.value
    try:
        return UserRole(normalized)
    except ValueError:
        return UserRole.USER


def to_admin_user_out(user: dict) -> AdminUserOut:
    return AdminUserOut(
        id=str(user["_id"]),
        name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        role=normalize_role(user.get("role")),
        is_active=bool(user.get("is_active", True)),
    )


def is_super_admin(user: dict) -> bool:
    return str(user.get("role", "")).strip().lower() == UserRole.SUPER_ADMIN.value


def _object_id_or_400(user_id: str) -> ObjectId:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")
    return ObjectId(user_id)


async def get_admin_dashboard_metrics() -> dict:
    users_collection = get_users_collection()
    total_users = await users_collection.count_documents({})
    active_users = await users_collection.count_documents({"is_active": True})
    inactive_users = await users_collection.count_documents({"is_active": False})
    admin_users = await users_collection.count_documents(
        {"role": {"$in": [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]}}
    )
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "admin_users": admin_users,
    }


async def list_admin_users() -> list[AdminUserOut]:
    users = await get_users_collection().find(
        {},
        {
            "name": 1,
            "email": 1,
            "phone": 1,
            "role": 1,
            "is_active": 1,
        },
    ).to_list(length=1000)
    return [to_admin_user_out(user) for user in users]


async def update_user_role(user_id: str, payload: UserRoleUpdate, current_user: dict) -> AdminUserOut:
    object_id = _object_id_or_400(user_id)
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin role cannot be assigned here")

    users_collection = get_users_collection()
    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_super_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin accounts are locked")
    if str(current_user.get("_id")) == user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot change your own role")

    result = await users_collection.update_one({"_id": object_id}, {"$set": {"role": payload.role.value}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_admin_user_out(user)


async def update_user_status(user_id: str, payload: UserStatusUpdate, current_user: dict) -> AdminUserOut:
    object_id = _object_id_or_400(user_id)
    users_collection = get_users_collection()
    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_super_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin accounts are locked")
    if str(current_user.get("_id")) == user_id and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot deactivate your own account")

    result = await users_collection.update_one({"_id": object_id}, {"$set": {"is_active": payload.is_active}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_admin_user_out(user)


async def update_admin_user(user_id: str, payload: UserUpdate) -> AdminUserOut:
    object_id = _object_id_or_400(user_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    users_collection = get_users_collection()
    if "email" in updates:
        existing = await users_collection.find_one({"email": updates["email"], "_id": {"$ne": object_id}})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    result = await users_collection.update_one({"_id": object_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_admin_user_out(user)


async def delete_admin_user(user_id: str, current_user: dict) -> None:
    object_id = _object_id_or_400(user_id)
    if str(current_user.get("_id")) == user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete your own account")

    users_collection = get_users_collection()
    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_super_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin accounts are locked")

    result = await users_collection.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
