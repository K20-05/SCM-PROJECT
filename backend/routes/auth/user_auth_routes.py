from fastapi import APIRouter, Depends, Request, status

from auth.access_control import require_role
from auth.auth_deps import get_current_user
from auth.captcha import captcha_config, create_local_captcha, verify_login_captcha
from auth.rate_limit import auth_rate_limit
from backend.models.auth_models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
    UserSignup,
    UserUpdate,
)
from backend.services.admin_user_service import delete_admin_user
from backend.services.user_service import (
    change_user_password,
    create_manual_user,
    get_visible_user,
    list_users_for_admin,
    login_user,
    request_password_reset,
    reset_user_password,
    signup_user,
    token_for_user,
    update_visible_user,
    user_out_from_document,
)


router = APIRouter(prefix="/api/auth", tags=["Auth"])
user_crud_router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_rate_limit)])
async def signup(payload: UserSignup):
    return await signup_user(payload)


@router.post("/login", response_model=Token, dependencies=[Depends(auth_rate_limit)])
async def login(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        # Swagger OAuth2 password flow sends username/password.
        data = {
            "email": str(form.get("username") or form.get("email") or "").strip(),
            "password": str(form.get("password") or ""),
            "recaptcha_token": form.get("recaptcha_token"),
            "captcha_id": form.get("captcha_id"),
            "captcha_answer": form.get("captcha_answer"),
        }
    else:
        data = await request.json()

    payload = UserLogin.model_validate(data)
    await verify_login_captcha(data, request)
    email = payload.email
    password = payload.password

    return await login_user(email, password)


@router.get("/captcha/config", include_in_schema=False)
async def get_captcha_config():
    return captcha_config()


@router.get("/captcha", include_in_schema=False)
async def get_captcha():
    return create_local_captcha()


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    return user_out_from_document(current_user)


@router.post("/change-password", dependencies=[Depends(auth_rate_limit)])
async def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    return await change_user_password(payload, current_user)


@router.post("/forgot-password", dependencies=[Depends(auth_rate_limit)])
async def forgot_password(payload: ForgotPasswordRequest):
    return await request_password_reset(payload)


@router.post("/reset-password", dependencies=[Depends(auth_rate_limit)])
async def reset_password(payload: ResetPasswordRequest):
    return await reset_user_password(payload)


@router.post("/refresh", response_model=Token)
async def refresh_access_token(current_user: dict = Depends(get_current_user)):
    return token_for_user(current_user)


@user_crud_router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("admin"))])
async def create_user(payload: UserCreate):
    return await create_manual_user(payload)


@user_crud_router.get("", dependencies=[Depends(require_role("admin"))])
async def list_users():
    return await list_users_for_admin()


@user_crud_router.get("/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    return await get_visible_user(user_id, current_user)


@user_crud_router.put("/me")
async def update_me(payload: UserUpdate, current_user: dict = Depends(get_current_user)):
    return await update_visible_user(str(current_user["_id"]), payload)


@user_crud_router.put("/{user_id}", dependencies=[Depends(require_role("super_admin"))], include_in_schema=False)
async def update_user(user_id: str, payload: UserUpdate):
    return await update_visible_user(user_id, payload)


@user_crud_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, current_user: dict = Depends(require_role("super_admin"))):
    await delete_admin_user(user_id, current_user)
    return None
