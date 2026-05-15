from enum import Enum

from pydantic import BaseModel, EmailStr, ValidationInfo, field_validator


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


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


class UserLogin(BaseModel):
    email: EmailStr
    password: str


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
