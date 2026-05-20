from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticDatabase
from pymongo.errors import CollectionInvalid
from auth.auth_utils import hash_password
from backend.config.app_config import settings
from backend.models.auth_models import UserRole

client: AsyncIOMotorClient | None = None
database: AgnosticDatabase | None = None


async def connect_to_mongo() -> None:
    global client, database
    if client is not None and database is not None:
        return
    if not settings.mongo_url:
        raise RuntimeError("MONGO_URL (or MONGODB_URL) is required in .env")
    client = AsyncIOMotorClient(settings.mongo_url)
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
    await users_collection.create_index("email", unique=True)
    try:
        await users_collection.drop_index("phone_1")
    except Exception:
        pass
    await users_collection.create_index("phone")
    await users_collection.create_index("role")
    await logins_collection.create_index("email")
    await logins_collection.create_index("logged_in_at")
    await sensor_data_collection.create_index("device_id")
    await sensor_data_collection.create_index("recorded_at")
    await shipments_collection.create_index("tracking_id", unique=True)
    await shipments_collection.create_index("owner_id")
    await shipments_collection.create_index("status")


async def ensure_default_admin() -> None:
    users_collection = get_users_collection()

    existing_admin = await users_collection.find_one({"role": UserRole.ADMIN.value})
    if existing_admin:
        return

    admin_email = settings.admin_email.strip()
    admin_password = settings.admin_password
    admin_phone = settings.admin_phone.strip()
    admin_name = settings.admin_name.strip() or "System Admin"

    if not admin_email or not admin_password or not admin_phone:
        return

    existing_user = await users_collection.find_one({"email": admin_email})
    if existing_user:
        await users_collection.update_one(
            {"_id": existing_user["_id"]},
            {
                "$set": {
                    "role": UserRole.ADMIN.value,
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return

    await users_collection.insert_one(
        {
            "name": admin_name,
            "email": admin_email,
            "phone": admin_phone,
            "hashed_password": hash_password(admin_password),
            "role": UserRole.ADMIN.value,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_active": True,
        }
    )


async def ensure_database_setup() -> None:
    await connect_to_mongo()
    await ensure_collections()
    await ensure_indexes()
    await ensure_default_admin()
