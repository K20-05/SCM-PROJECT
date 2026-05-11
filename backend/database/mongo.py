from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid
from backend.config.app_config import (
    LOGINS_COLLECTION_NAME,
    MONGODB_DB_NAME,
    MONGODB_URL,
    SENSOR_DATA_COLLECTION_NAME,
    SHIPMENTS_COLLECTION_NAME,
    USERS_COLLECTION_NAME,
)

if not MONGODB_URL:
    raise RuntimeError("MONGODB_URL is required in .env")
if not MONGODB_URL.startswith("mongodb+srv://"):
    raise RuntimeError("MONGODB_URL must be an Atlas SRV URI (mongodb+srv://...)")

client = AsyncIOMotorClient(MONGODB_URL)
database = client[MONGODB_DB_NAME]

def get_database():
    return database


def get_collection(collection_name: str):
    return database[collection_name]


users_collection = get_collection(USERS_COLLECTION_NAME)
logins_collection = get_collection(LOGINS_COLLECTION_NAME)
sensor_data_collection = get_collection(SENSOR_DATA_COLLECTION_NAME)
shipments_collection = get_collection(SHIPMENTS_COLLECTION_NAME)


async def test_database_connection() -> None:
    # Ping validates that credentials, DNS, and cluster connectivity are healthy.
    await client.admin.command("ping")


async def ensure_collections() -> None:
    existing = await database.list_collection_names()

    if USERS_COLLECTION_NAME not in existing:
        try:
            await database.create_collection(USERS_COLLECTION_NAME)
        except CollectionInvalid:
            pass

    if LOGINS_COLLECTION_NAME not in existing:
        try:
            await database.create_collection(LOGINS_COLLECTION_NAME)
        except CollectionInvalid:
            pass

    if SENSOR_DATA_COLLECTION_NAME not in existing:
        try:
            await database.create_collection(SENSOR_DATA_COLLECTION_NAME)
        except CollectionInvalid:
            pass

    if SHIPMENTS_COLLECTION_NAME not in existing:
        try:
            await database.create_collection(SHIPMENTS_COLLECTION_NAME)
        except CollectionInvalid:
            pass


async def ensure_indexes() -> None:
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("phone", unique=True)
    await users_collection.create_index("role")
    await logins_collection.create_index("email")
    await logins_collection.create_index("logged_in_at")
    await sensor_data_collection.create_index("device_id")
    await sensor_data_collection.create_index("recorded_at")
    await shipments_collection.create_index("shipment_id", unique=True)
    await shipments_collection.create_index("status")


async def ensure_database_setup() -> None:
    await test_database_connection()
    await ensure_collections()
    await ensure_indexes()
