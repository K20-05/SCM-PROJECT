import json

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ROLES = [
    {"name": "user", "level": 10},
    {"name": "admin", "level": 50},
    {"name": "super_admin", "level": 100},
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_url: str = Field(validation_alias=AliasChoices("MONGO_URL", "MONGODB_URL"))
    db_name: str = Field(default="scm_project", validation_alias=AliasChoices("DB_NAME", "MONGODB_DB_NAME"))
    jwt_secret: str = Field(
        default="change-me-in-env",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_expire_minutes: int = Field(default=60, validation_alias="JWT_EXPIRE_MINUTES")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    environment: str = Field(default="dev", validation_alias="ENVIRONMENT")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    default_role: str = Field(default="user", validation_alias="DEFAULT_ROLE")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")

    users_collection_name: str = Field(default="users", validation_alias="USERS_COLLECTION_NAME")
    logins_collection_name: str = Field(default="logins", validation_alias="LOGINS_COLLECTION_NAME")
    sensor_data_collection_name: str = Field(default="sensor_data", validation_alias="SENSOR_DATA_COLLECTION_NAME")
    shipments_collection_name: str = Field(default="shipments", validation_alias="SHIPMENTS_COLLECTION_NAME")
    admin_email: str = Field(default="", validation_alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    admin_name: str = Field(default="System Admin", validation_alias="ADMIN_NAME")
    admin_phone: str = Field(default="", validation_alias="ADMIN_PHONE")
    default_roles_json: str = Field(default="", validation_alias="DEFAULT_ROLES_JSON")


settings = Settings()


def get_settings() -> Settings:
    return settings


def load_role_seed_data() -> list[dict]:
    raw_role_data = settings.default_roles_json.strip()
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
