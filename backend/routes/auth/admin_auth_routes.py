from fastapi import APIRouter, Depends, status

from auth.access_control import require_role
from backend.models.auth_models import AdminUserOut, UserRoleUpdate, UserStatusUpdate, UserUpdate
from backend.services.admin_user_service import (
    delete_admin_user,
    get_admin_dashboard_metrics,
    list_admin_users,
    update_admin_user,
    update_user_role as update_user_role_service,
    update_user_status as update_user_status_service,
)


router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(_current_user: dict = Depends(require_role("admin"))):
    return await get_admin_dashboard_metrics()


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_current_user: dict = Depends(require_role("admin"))):
    return await list_admin_users()


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    current_user: dict = Depends(require_role("super_admin")),
):
    return await update_user_role_service(user_id, payload, current_user)


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    current_user: dict = Depends(require_role("super_admin")),
):
    return await update_user_status_service(user_id, payload, current_user)


@router.put("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    _current_user: dict = Depends(require_role("admin")),
):
    return await update_admin_user(user_id, payload)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    await delete_admin_user(user_id, current_user)
    return None
