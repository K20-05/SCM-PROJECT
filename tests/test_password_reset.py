import asyncio
from datetime import timedelta

from bson import ObjectId
from fastapi import HTTPException, status

from auth.auth_utils import hash_password, verify_password
from backend.models.auth_models import ForgotPasswordRequest, ResetPasswordRequest
from backend.services import user_service
from backend.services.service_helpers import now_utc


class _FakeUsersCollection:
    def __init__(self, user: dict | None):
        self.user = user

    async def find_one(self, query: dict, projection: dict | None = None):
        if not self.user:
            return None
        if query.get("email") and query["email"] != self.user.get("email"):
            return None
        return self.user

    async def update_one(self, query: dict, update: dict):
        if not self.user or query.get("_id") != self.user.get("_id"):
            return None
        self.user.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            self.user.pop(key, None)
        return None


def _active_user():
    return {
        "_id": ObjectId(),
        "email": "user@example.com",
        "hashed_password": hash_password("OldPassword123"),
        "is_active": True,
        "is_deleted": False,
    }


def test_password_reset_request_returns_development_token(monkeypatch):
    user = _active_user()
    users = _FakeUsersCollection(user)
    monkeypatch.setattr(user_service, "get_users_collection", lambda: users)
    monkeypatch.setattr(user_service.app_settings, "environment", "dev")
    monkeypatch.setattr(user_service.app_settings, "smtp_host", "")
    monkeypatch.setattr(user_service.app_settings, "smtp_from_email", "")

    result = asyncio.run(user_service.request_password_reset(ForgotPasswordRequest(email=user["email"])))

    assert result["message"] == "Email is not configured, so the reset token is shown here for testing."
    assert result["reset_token"]
    assert user["password_reset_token_hash"] == user_service._hash_reset_token(result["reset_token"])
    assert user["password_reset_expires_at"] > now_utc()


def test_password_reset_updates_hash_and_clears_token(monkeypatch):
    user = _active_user()
    token = "reset-token"
    user["password_reset_token_hash"] = user_service._hash_reset_token(token)
    user["password_reset_expires_at"] = now_utc() + timedelta(minutes=5)
    users = _FakeUsersCollection(user)
    monkeypatch.setattr(user_service, "get_users_collection", lambda: users)

    result = asyncio.run(
        user_service.reset_user_password(
            ResetPasswordRequest(
                email=user["email"],
                reset_token=token,
                new_password="NewPassword123",
                confirm_new_password="NewPassword123",
            )
        )
    )

    assert result["message"] == "Password reset successfully. You can now log in."
    assert verify_password("NewPassword123", user["hashed_password"])
    assert "password_reset_token_hash" not in user
    assert "password_reset_expires_at" not in user


def test_password_reset_rejects_expired_token(monkeypatch):
    user = _active_user()
    user["password_reset_token_hash"] = user_service._hash_reset_token("expired-token")
    user["password_reset_expires_at"] = now_utc() - timedelta(minutes=1)
    users = _FakeUsersCollection(user)
    monkeypatch.setattr(user_service, "get_users_collection", lambda: users)

    with_exception = None
    try:
        asyncio.run(
            user_service.reset_user_password(
                ResetPasswordRequest(
                    email=user["email"],
                    reset_token="expired-token",
                    new_password="NewPassword123",
                    confirm_new_password="NewPassword123",
                )
            )
        )
    except HTTPException as exc:
        with_exception = exc

    assert with_exception is not None
    assert with_exception.status_code == status.HTTP_400_BAD_REQUEST
