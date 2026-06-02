from fastapi import APIRouter, Depends

from auth.access_control import require_role
from auth.auth_deps import get_current_user
from backend.services.dashboard_service import (
    admin_dashboard as admin_dashboard_service,
    current_dashboard as current_dashboard_service,
    super_admin_dashboard as super_admin_dashboard_service,
    user_dashboard as user_dashboard_service,
)


router = APIRouter(prefix="/api/dashboard", tags=["Dashboards"], include_in_schema=False)


@router.get("/me")
async def current_dashboard(current_user: dict = Depends(get_current_user)):
    return await current_dashboard_service(current_user)


@router.get("/user")
async def user_dashboard(current_user: dict = Depends(get_current_user)):
    return await user_dashboard_service(current_user)


@router.get("/admin")
async def admin_dashboard(current_user: dict = Depends(require_role("admin"))):
    return await admin_dashboard_service(current_user)


@router.get("/super-admin")
async def super_admin_dashboard(current_user: dict = Depends(require_role("super_admin"))):
    return await super_admin_dashboard_service(current_user)
