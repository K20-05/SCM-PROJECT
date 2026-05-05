import os
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "scm_project")

client = AsyncIOMotorClient(MONGODB_URL)
database = client[MONGODB_DB_NAME]
users_collection = database["users"]
logins_collection = database["logins"]


async def ensure_indexes() -> None:
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("phone", unique=True)
    await logins_collection.create_index("email")
    await logins_collection.create_index("logged_in_at")
