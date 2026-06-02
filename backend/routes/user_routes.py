from fastapi import APIRouter, Depends

from auth.access_control import require_role
from auth.auth_deps import get_current_user
from backend.models.auth_models import ChangePasswordRequest, UserLogin, UserSignup
from backend.services.user_service import change_user_password, login_user, signup_user


# Kept as an inactive legacy compatibility module. main.py does not include this router.
router = APIRouter(prefix="/user", tags=["User"])


@router.post("/signup")
async def signup(user: UserSignup):
    created = await signup_user(user)
    return {
        "message": "User registered successfully",
        "user": created.model_dump(),
    }


@router.post("/login")
async def login(user: UserLogin):
    token = await login_user(user.email, user.password)
    return {
        "message": "Login successful",
        "token_type": token.token_type,
        "access_token": token.access_token,
        "role": token.role,
        "dashboard_url": token.dashboard_url,
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    return await change_user_password(payload, current_user)


@router.get("/admin-only")
async def admin_only(_current_user: dict = Depends(require_role("admin"))):
    return {"message": "Admin access granted"}


@router.get("/super-admin-only")
async def super_admin_only(_current_user: dict = Depends(require_role("super_admin"))):
    return {"message": "Super admin access granted"}
