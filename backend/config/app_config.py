import json
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)


MONGODB_URL = os.getenv("MONGODB_URL")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "scm_project")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-env")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "user").strip().lower()

def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required in .env")
    return value


USERS_COLLECTION_NAME = get_required_env("USERS_COLLECTION_NAME")
LOGINS_COLLECTION_NAME = get_required_env("LOGINS_COLLECTION_NAME")
SENSOR_DATA_COLLECTION_NAME = get_required_env("SENSOR_DATA_COLLECTION_NAME")
SHIPMENTS_COLLECTION_NAME = get_required_env("SHIPMENTS_COLLECTION_NAME")

DEFAULT_ROLES = [
    {"name": "user", "level": 10},
    {"name": "admin", "level": 50},
    {"name": "super_admin", "level": 100},
]


def load_role_seed_data() -> list[dict]:
    raw_role_data = os.getenv("DEFAULT_ROLES_JSON", "").strip()
    if not raw_role_data:
        return DEFAULT_ROLES

    try:
        parsed = json.loads(raw_role_data)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DEFAULT_ROLES_JSON must be valid JSON") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("DEFAULT_ROLES_JSON must be a JSON array")

    normalized_roles: list[dict] = []
    for role in parsed:
        if not isinstance(role, dict):
            raise RuntimeError("Every role in DEFAULT_ROLES_JSON must be an object")

        name = str(role.get("name", "")).strip().lower()
        level = role.get("level")
        if not name:
            raise RuntimeError("Role name is required in DEFAULT_ROLES_JSON")
        if not isinstance(level, int):
            raise RuntimeError(f"Role level must be an integer for role '{name}'")

        normalized_roles.append({"name": name, "level": level})

    return normalized_roles
