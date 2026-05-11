from backend.database.mongo import (
    get_collection,
    get_database,
    test_database_connection,
)


async def is_database_alive() -> bool:
    try:
        await test_database_connection()
        return True
    except Exception:
        return False


def users_collection():
    return get_collection("users")


def logins_collection():
    return get_collection("logins")


def database_name() -> str:
    return get_database().name
