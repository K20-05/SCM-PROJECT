import asyncio

from bson import ObjectId
from fastapi import HTTPException, status

from backend.models.auth_models import UserRole, UserRoleUpdate
from backend.routes.auth import user_auth_routes
from backend.services import admin_user_service, user_service


class _FakeUsersCollection:
    def __init__(self, user: dict | None = None):
        self.user = user

    async def find_one(self, query: dict, projection: dict | None = None):
        return self.user


class _FakeRoleUsersCollection:
    def __init__(self, user: dict):
        self.user = user

    async def find_one(self, query: dict, projection: dict | None = None):
        if self.user.get("is_deleted") is True:
            return None
        return dict(self.user)

    async def update_one(self, query: dict, update: dict):
        if self.user.get("is_deleted") is True:
            return type("UpdateResult", (), {"matched_count": 0})()
        self.user.update(update.get("$set", {}))
        return type("UpdateResult", (), {"matched_count": 1})()


def test_inactive_user_cannot_login(monkeypatch):
    monkeypatch.setattr(
        user_service,
        "get_users_collection",
        lambda: _FakeUsersCollection(
            {
                "_id": ObjectId(),
                "email": "inactive@example.com",
                "is_active": False,
                "hashed_password": "unused",
            }
        ),
    )

    with_exception = None
    try:
        asyncio.run(user_service.login_user("inactive@example.com", "password"))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == status.HTTP_403_FORBIDDEN
    assert with_exception.detail == "Account is inactive"


def test_super_admin_cannot_delete_self():
    user_id = str(ObjectId())

    with_exception = None
    try:
        asyncio.run(admin_user_service.delete_admin_user(user_id, {"_id": user_id, "role": "super_admin"}))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == status.HTTP_403_FORBIDDEN
    assert with_exception.detail == "You cannot delete your own account"


def test_users_delete_endpoint_cannot_delete_self():
    user_id = str(ObjectId())

    with_exception = None
    try:
        asyncio.run(user_auth_routes.delete_user(user_id, {"_id": user_id, "role": "super_admin"}))
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == status.HTTP_403_FORBIDDEN
    assert with_exception.detail == "You cannot delete your own account"


def test_super_admin_can_promote_user_to_super_admin(monkeypatch):
    user_id = ObjectId()
    fake = _FakeRoleUsersCollection(
        {
            "_id": user_id,
            "name": "User",
            "email": "user@example.com",
            "phone": "9876543210",
            "role": "user",
            "is_active": True,
        }
    )
    monkeypatch.setattr(admin_user_service, "get_users_collection", lambda: fake)

    result = asyncio.run(
        admin_user_service.update_user_role(
            str(user_id),
            UserRoleUpdate(role=UserRole.SUPER_ADMIN),
            {"_id": str(ObjectId()), "role": "super_admin"},
        )
    )

    assert result.role == UserRole.SUPER_ADMIN


def test_super_admin_can_demote_another_super_admin(monkeypatch):
    user_id = ObjectId()
    fake = _FakeRoleUsersCollection(
        {
            "_id": user_id,
            "name": "Peer",
            "email": "peer@example.com",
            "phone": "9876543211",
            "role": "super_admin",
            "is_active": True,
        }
    )
    monkeypatch.setattr(admin_user_service, "get_users_collection", lambda: fake)

    result = asyncio.run(
        admin_user_service.update_user_role(
            str(user_id),
            UserRoleUpdate(role=UserRole.ADMIN),
            {"_id": str(ObjectId()), "role": "super_admin"},
        )
    )

    assert result.role == UserRole.ADMIN


def test_super_admin_cannot_change_own_role():
    user_id = str(ObjectId())

    with_exception = None
    try:
        asyncio.run(
            admin_user_service.update_user_role(
                user_id,
                UserRoleUpdate(role=UserRole.USER),
                {"_id": user_id, "role": "super_admin"},
            )
        )
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == status.HTTP_403_FORBIDDEN
    assert with_exception.detail == "You cannot change your own role"
