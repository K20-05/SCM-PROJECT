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
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_expire_minutes: int = Field(default=60, validation_alias="JWT_EXPIRE_MINUTES")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    environment: str = Field(default="dev", validation_alias="ENVIRONMENT")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    default_role: str = Field(default="user", validation_alias="DEFAULT_ROLE")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    auth_rate_limit_requests: int = Field(default=5, validation_alias="AUTH_RATE_LIMIT_REQUESTS")
    auth_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    recaptcha_site_key: str = Field(default="", validation_alias="RECAPTCHA_SITE_KEY")
    recaptcha_secret_key: str = Field(default="", validation_alias="RECAPTCHA_SECRET_KEY")
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")

    users_collection_name: str = Field(default="users", validation_alias="USERS_COLLECTION_NAME")
    logins_collection_name: str = Field(default="login", validation_alias="LOGINS_COLLECTION_NAME")
    sensor_data_collection_name: str = Field(default="sensor_data", validation_alias="SENSOR_DATA_COLLECTION_NAME")
    shipments_collection_name: str = Field(default="shipments", validation_alias="SHIPMENTS_COLLECTION_NAME")
    devices_collection_name: str = Field(default="devices", validation_alias="DEVICES_COLLECTION_NAME")
    kafka_bootstrap_servers: str = Field(default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_device_topic: str = Field(default="device-data-stream", validation_alias="KAFKA_DEVICE_TOPIC")
    kafka_consumer_group: str = Field(default="scmxpertlite-device-consumers", validation_alias="KAFKA_CONSUMER_GROUP")
    admin_email: str = Field(default="", validation_alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    admin_name: str = Field(default="System Admin", validation_alias="ADMIN_NAME")
    admin_phone: str = Field(default="", validation_alias="ADMIN_PHONE")
    super_admin_email: str = Field(default="", validation_alias="SUPER_ADMIN_EMAIL")
    super_admin_password: str = Field(default="", validation_alias="SUPER_ADMIN_PASSWORD")
    super_admin_name: str = Field(default="Super Admin", validation_alias="SUPER_ADMIN_NAME")
    super_admin_phone: str = Field(default="", validation_alias="SUPER_ADMIN_PHONE")
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

