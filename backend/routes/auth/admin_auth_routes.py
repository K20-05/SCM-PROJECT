from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from auth.access_control import require_role
from backend.database.mongo import get_users_collection
from backend.models.auth_models import AdminUserOut, UserRole, UserRoleUpdate


router = APIRouter(prefix="/api/admin", tags=["Admin"])


def normalize_role(value: str | None) -> UserRole:
    normalized = (value or "").strip().lower()
    if normalized == "user":
        normalized = UserRole.CUSTOMER.value
    try:
        return UserRole(normalized)
    except ValueError:
        return UserRole.CUSTOMER


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
        AdminUserOut(
            id=str(user["_id"]),
            name=user.get("name", ""),
            email=user.get("email", ""),
            phone=user.get("phone", ""),
            role=normalize_role(user.get("role")),
            is_active=bool(user.get("is_active", True)),
        )
        for user in users
    ]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
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

    return AdminUserOut(
        id=str(user["_id"]),
        name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        role=normalize_role(user.get("role")),
        is_active=bool(user.get("is_active", True)),
    )


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
