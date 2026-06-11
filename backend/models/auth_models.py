from enum import Enum
import re

from pydantic import BaseModel, EmailStr, ValidationInfo, field_validator


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must be 10 digits")
        return value

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value, field_name="Password")
        return value


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must be 10 digits")
        return value


class UserSignup(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must be 10 digits")
        return value

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value, field_name="Password")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    recaptcha_token: str | None = None
    captcha_id: str | None = None
    captcha_answer: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return value

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value, field_name="New password")
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str
    confirm_new_password: str

    @field_validator("confirm_new_password")
    @classmethod
    def reset_passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return value

    @field_validator("new_password")
    @classmethod
    def reset_password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value, field_name="New password")
        return value


class UserOut(BaseModel):
    name: str
    email: EmailStr
    phone: str
    role: UserRole


class UserInDB(UserOut):
    hashed_password: str
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserStatusUpdate(BaseModel):
    is_active: bool


class AdminUserOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    role: UserRole
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole | None = None
    dashboard_url: str | None = None


def validate_password_strength(value: str, *, field_name: str) -> None:
    if len(value) < 8:
        raise ValueError(f"{field_name} must be at least 8 characters")
    if not re.search(r"[A-Z]", value):
        raise ValueError(f"{field_name} must include an uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError(f"{field_name} must include a lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError(f"{field_name} must include a number")
