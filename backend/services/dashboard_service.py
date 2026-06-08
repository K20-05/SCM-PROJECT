from datetime import datetime, time, timezone

from backend.database.mongo import (
    get_devices_collection,
    get_logins_collection,
    get_shipments_collection,
    get_users_collection,
)
from backend.models.auth_models import UserRole


def dashboard_path(role: str) -> str:
    paths = {
        UserRole.USER.value: "/dashboard/user",
        UserRole.ADMIN.value: "/dashboard/admin",
        UserRole.SUPER_ADMIN.value: "/dashboard/super-admin",
    }
    return paths.get(role, paths[UserRole.USER.value])


def user_summary(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "role": user.get("role", UserRole.USER.value),
        "is_active": bool(user.get("is_active", True)),
    }


async def current_dashboard(current_user: dict) -> dict:
    role = str(current_user.get("role", UserRole.USER.value)).strip().lower()
    return {
        "role": role,
        "dashboard_url": dashboard_path(role),
        "user": user_summary(current_user),
    }


async def user_dashboard(current_user: dict) -> dict:
    return {
        "role": UserRole.USER.value,
        "dashboard_url": dashboard_path(UserRole.USER.value),
        "user": user_summary(current_user),
        "permissions": [
            "view_own_account",
            "edit_own_display_name",
            "change_own_password",
            "create_shipment_requests",
        ],
        "restricted": [
            "role_management",
            "device_inventory_management",
            "full_user_roster",
            "platform_governance",
        ],
    }


async def admin_dashboard(current_user: dict) -> dict:
    users = get_users_collection()
    devices = get_devices_collection()
    shipments = get_shipments_collection()
    today_start, today_end = today_bounds()
    return {
        "role": UserRole.ADMIN.value,
        "dashboard_url": dashboard_path(UserRole.ADMIN.value),
        "user": user_summary(current_user),
        "metrics": {
            "users_managed": await users.count_documents({}),
            "active_users": await users.count_documents({"is_active": True}),
            "devices_monitored": await devices.count_documents({}),
            "available_devices": await devices.count_documents({"status": "available"}),
            "shipments_tracked": await shipments.count_documents({"is_deleted": {"$ne": True}}),
            "pending_shipments": await shipments.count_documents({"status": "pending", "is_deleted": {"$ne": True}}),
            "todays_deliveries": await shipments.count_documents(
                {
                    "expected_delivery_date": {"$gte": today_start, "$lte": today_end},
                    "is_deleted": {"$ne": True},
                }
            ),
            "access_level": "operations",
        },
        "permissions": [
            "view_users",
            "view_devices",
            "view_shipments",
            "create_shipment_requests",
            "manage_devices",
            "manage_shipments",
            "change_own_password",
        ],
        "restricted": [
            "promote_users",
            "demote_admins",
            "delete_users",
            "super_admin_governance",
        ],
    }


async def super_admin_dashboard(current_user: dict) -> dict:
    users = get_users_collection()
    devices = get_devices_collection()
    shipments = get_shipments_collection()
    recent_logins = await get_logins_collection().find(
        {},
        {"_id": 0, "name": 1, "email": 1, "role": 1, "logged_in_at": 1},
    ).sort("logged_in_at", -1).to_list(length=5)
    today_start, today_end = today_bounds()
    return {
        "role": UserRole.SUPER_ADMIN.value,
        "dashboard_url": dashboard_path(UserRole.SUPER_ADMIN.value),
        "user": user_summary(current_user),
        "metrics": {
            "total_users": await users.count_documents({}),
            "admin_count": await users.count_documents(
                {"role": {"$in": [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]}}
            ),
            "active_users": await users.count_documents({"is_active": True}),
            "inactive_users": await users.count_documents({"is_active": False}),
            "devices_monitored": await devices.count_documents({}),
            "available_devices": await devices.count_documents({"status": "available"}),
            "assigned_devices": await devices.count_documents({"status": "assigned"}),
            "shipments_tracked": await shipments.count_documents({"is_deleted": {"$ne": True}}),
            "pending_shipments": await shipments.count_documents({"status": "pending", "is_deleted": {"$ne": True}}),
            "todays_deliveries": await shipments.count_documents(
                {
                    "expected_delivery_date": {"$gte": today_start, "$lte": today_end},
                    "is_deleted": {"$ne": True},
                }
            ),
            "in_transit_shipments": await shipments.count_documents(
                {"status": "in_transit", "is_deleted": {"$ne": True}}
            ),
            "platform_health": "online",
            "access_level": "governance",
        },
        "recent_logins": recent_logins,
        "permissions": [
            "view_all_users",
            "view_admins",
            "promote_users",
            "demote_admins",
            "inspect_backend_health",
            "inspect_database_status",
            "change_own_password",
        ],
        "restricted": [
            "edit_super_admin_role",
            "self_downgrade",
        ],
    }


def today_bounds() -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    return (
        datetime.combine(today, time.min, tzinfo=timezone.utc),
        datetime.combine(today, time.max, tzinfo=timezone.utc),
    )
