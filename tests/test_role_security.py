import asyncio

from bson import ObjectId
from fastapi import HTTPException, status

from backend.services import admin_user_service, user_service


class _FakeUsersCollection:
    def __init__(self, user: dict | None = None):
        self.user = user

    async def find_one(self, query: dict, projection: dict | None = None):
        return self.user


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
