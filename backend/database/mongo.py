from datetime import datetime, timezone

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticDatabase
from pymongo.errors import CollectionInvalid, DuplicateKeyError
from auth.auth_utils import hash_password
from backend.config.app_config import settings
from backend.models.auth_models import UserRole

client: AsyncIOMotorClient | None = None
database: AgnosticDatabase | None = None
WEAK_ADMIN_PASSWORDS = {
    "admin",
    "admin123",
    "admin@123",
    "password",
    "password123",
    "changeme",
    "changeit",
    "12345678",
}


async def connect_to_mongo() -> None:
    global client, database
    if client is not None and database is not None:
        return
    if not settings.mongo_url:
        raise RuntimeError("MONGO_URL (or MONGODB_URL) is required in .env")
    client = AsyncIOMotorClient(settings.mongo_url, tlsCAFile=certifi.where())
    database = client[settings.db_name]
    await client.admin.command("ping")


async def close_mongo_connection() -> None:
    global client, database
    if client is not None:
        client.close()
    client = None
    database = None


def get_db() -> AgnosticDatabase:
    if database is None:
        raise RuntimeError("Mongo database is not initialized. Call connect_to_mongo() at startup.")
    return database


def get_database():
    return get_db()


def get_collection(collection_name: str):
    return get_db()[collection_name]


def get_users_collection():
    return get_collection(settings.users_collection_name)


def get_logins_collection():
    return get_collection(settings.logins_collection_name)


def get_sensor_data_collection():
    return get_collection(settings.sensor_data_collection_name)


def get_shipments_collection():
    return get_collection(settings.shipments_collection_name)


def get_devices_collection():
    return get_collection(settings.devices_collection_name)


async def test_database_connection() -> None:
    # Ping validates that credentials, DNS, and cluster connectivity are healthy.
    await get_db().client.admin.command("ping")


async def ensure_collections() -> None:
    db = get_db()
    existing = await db.list_collection_names()
    required_collections = [
        settings.users_collection_name,
        settings.logins_collection_name,
        settings.sensor_data_collection_name,
        settings.shipments_collection_name,
        settings.devices_collection_name,
    ]

    for collection_name in required_collections:
        if collection_name in existing:
            continue
        try:
            await db.create_collection(collection_name)
        except CollectionInvalid:
            pass


async def ensure_indexes() -> None:
    users_collection = get_users_collection()
    logins_collection = get_logins_collection()
    sensor_data_collection = get_sensor_data_collection()
    shipments_collection = get_shipments_collection()
    devices_collection = get_devices_collection()
    await users_collection.create_index("email", unique=True)
    try:
        await users_collection.drop_index("phone_1")
    except Exception:
        pass
    try:
        await users_collection.create_index("phone", unique=True, sparse=True)
    except DuplicateKeyError:
        await users_collection.create_index("phone")
    await users_collection.create_index("role")
    await logins_collection.create_index("email")
    await logins_collection.create_index("logged_in_at")
    await sensor_data_collection.create_index("device_id")
    await sensor_data_collection.create_index("recorded_at")
    await shipments_collection.create_index("tracking_id", unique=True)
    await shipments_collection.create_index("owner_id")
    await shipments_collection.create_index("status")
    await devices_collection.create_index("device_id", unique=True)
    await devices_collection.create_index("status")


def _validate_seed_password(password: str, env_name: str) -> None:
    normalized_password = password.strip().lower()
    if len(password) < 12 or normalized_password in WEAK_ADMIN_PASSWORDS:
        raise RuntimeError(
            f"{env_name} is too weak. Use at least 12 characters and avoid common/default passwords."
        )


async def ensure_seed_account(
    *,
    email: str,
    password: str,
    phone: str,
    name: str,
    role: UserRole,
    password_env_name: str,
) -> None:
    seed_email = email.strip()
    seed_password = password
    seed_phone = phone.strip()
    seed_name = name.strip() or role.value.replace("_", " ").title()

    if not seed_email or not seed_password or not seed_phone:
        return

    _validate_seed_password(seed_password, password_env_name)
    users_collection = get_users_collection()
    existing_user = await users_collection.find_one({"email": seed_email})
    if existing_user:
        await users_collection.update_one(
            {"_id": existing_user["_id"]},
            {
                "$set": {
                    "name": seed_name,
                    "phone": seed_phone,
                    "hashed_password": hash_password(seed_password),
                    "role": role.value,
                    "is_active": True,
                    "is_deleted": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return

    await users_collection.insert_one(
        {
            "name": seed_name,
            "email": seed_email,
            "phone": seed_phone,
            "hashed_password": hash_password(seed_password),
            "role": role.value,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_active": True,
        }
    )


async def ensure_default_accounts() -> None:
    await ensure_seed_account(
        email=settings.admin_email,
        password=settings.admin_password,
        phone=settings.admin_phone,
        name=settings.admin_name,
        role=UserRole.ADMIN,
        password_env_name="ADMIN_PASSWORD",
    )
    await ensure_seed_account(
        email=settings.super_admin_email,
        password=settings.super_admin_password,
        phone=settings.super_admin_phone,
        name=settings.super_admin_name,
        role=UserRole.SUPER_ADMIN,
        password_env_name="SUPER_ADMIN_PASSWORD",
    )


async def ensure_database_setup() -> None:
    await connect_to_mongo()
    await ensure_collections()
    await ensure_indexes()
    await ensure_default_accounts()
