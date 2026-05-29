from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from auth.access_control import require_role
from backend.database.mongo import get_users_collection
from backend.models.auth_models import AdminUserOut, UserRole, UserRoleUpdate, UserStatusUpdate, UserUpdate


router = APIRouter(prefix="/api/admin", tags=["Admin"])


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


@router.get("/dashboard")
async def admin_dashboard(_current_user: dict = Depends(require_role("admin"))):
    users_collection = get_users_collection()
    total_users = await users_collection.count_documents({})
    active_users = await users_collection.count_documents({"is_active": True})
    inactive_users = await users_collection.count_documents({"is_active": False})
    admin_users = await users_collection.count_documents({"role": {"$in": [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]}})
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "admin_users": admin_users,
    }


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_current_user: dict = Depends(require_role("admin"))):
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

    return [
        to_admin_user_out(user)
        for user in users
    ]


@router.patch("/users/{id}/role", response_model=AdminUserOut)
@router.patch("/users/{user_id}/role", response_model=AdminUserOut, include_in_schema=False)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    _current_user: dict = Depends(require_role("admin")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    users_collection = get_users_collection()
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": payload.role.value}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return to_admin_user_out(user)


@router.patch("/users/{id}/status", response_model=AdminUserOut)
@router.patch("/users/{user_id}/status", response_model=AdminUserOut, include_in_schema=False)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    _current_user: dict = Depends(require_role("admin")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    users_collection = get_users_collection()
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": payload.is_active}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return to_admin_user_out(user)


@router.put("/users/{id}", response_model=AdminUserOut)
@router.put("/users/{user_id}", response_model=AdminUserOut, include_in_schema=False)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    _current_user: dict = Depends(require_role("admin")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    users_collection = get_users_collection()
    if "email" in updates:
        existing = await users_collection.find_one({"email": updates["email"], "_id": {"$ne": ObjectId(user_id)}})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    result = await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_admin_user_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    _current_user: dict = Depends(require_role("admin")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

    result = await get_users_collection().delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return None
