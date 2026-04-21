import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException

from backend.db.database import users_collection


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-env")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


def generate_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_email: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, str | int] = {
        "sub": user_email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return _encode_jwt(payload)


def decode_access_token(token: str) -> dict:
    try:
        return _decode_jwt(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return token


async def get_user_by_email(email: str) -> dict | None:
    return await users_collection.find_one({"email": email})


def get_user_data(user_document: dict) -> dict:
    return {
        "name": user_document["name"],
        "email": user_document["email"],
        "phone": user_document["phone"],
    }


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(signing_input: bytes) -> str:
    signature = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64url_encode(signature)


def _encode_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    return f"{header_b64}.{payload_b64}.{_sign(signing_input)}"


def _decode_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token")
    header_b64, payload_b64, provided_signature = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid signature")

    header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    if header.get("typ") != "JWT":
        raise ValueError("Invalid header")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("Missing exp")
    if int(datetime.now(timezone.utc).timestamp()) >= exp:
        raise ValueError("Token expired")
    return payload
