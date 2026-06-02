import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException
import pytest
from pymongo.errors import DuplicateKeyError

from backend.models.auth_models import ChangePasswordRequest, UserCreate, UserSignup
from backend.routes.auth import user_auth_routes
from backend.services import user_service


class _FakeUsersCollection:
    def __init__(self):
        self.by_email: dict[str, dict] = {}
        self.by_id: dict[str, dict] = {}

    async def find_one(self, query: dict, projection: dict | None = None):
        if "email" in query:
            return self.by_email.get(query["email"])
        key = str(query["_id"])
        user = self.by_id.get(key)
        if not user:
            return None
        if projection is None:
            return dict(user)
        return {k: v for k, v in user.items() if projection.get(k, 1) != 0}

    async def insert_one(self, document: dict):
        if document["email"] in self.by_email:
            raise DuplicateKeyError("duplicate email")
        _id = ObjectId()
        stored = {"_id": _id, **document}
        self.by_email[document["email"]] = stored
        self.by_id[str(_id)] = stored
        return type("InsertResult", (), {"inserted_id": _id})()


def test_create_user_duplicate_email_returns_409(monkeypatch):
    fake = _FakeUsersCollection()
    fake.by_email["dup@example.com"] = {"_id": ObjectId(), "email": "dup@example.com"}
    monkeypatch.setattr(user_service, "get_users_collection", lambda: fake)

    with_exception = None
    try:
        asyncio.run(
            user_auth_routes.create_user(
                UserCreate(name="A", email="dup@example.com", phone="9876543210", password="Strong123"),
            )
        )
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == 409


def test_backend_user_validation_enforces_phone_and_password_rules():
    with pytest.raises(ValueError):
        UserSignup(
            name="Demo",
            email="demo@example.com",
            phone="123",
            password="weak",
            confirm_password="weak",
        )

    with pytest.raises(ValueError):
        ChangePasswordRequest(
            old_password="OldStrong1",
            new_password="lowercaseonly",
            confirm_new_password="lowercaseonly",
        )


def test_get_user_excludes_id_and_password(monkeypatch):
    fake = _FakeUsersCollection()
    user_id = ObjectId()
    fake.by_id[str(user_id)] = {
        "_id": user_id,
        "name": "Demo",
        "email": "demo@example.com",
        "password": "plain-text",
        "created_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(user_service, "get_users_collection", lambda: fake)

    result = asyncio.run(user_auth_routes.get_user(str(user_id), current_user={"_id": user_id, "role": "user"}))

    assert "_id" not in result
    assert "password" not in result
    assert result["email"] == "demo@example.com"
