import re

from pydantic import BaseModel, ValidationInfo, field_validator


class UserSignup(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    confirm_password: str

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, value):
            raise ValueError("Invalid email address")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must be 10 digits")
        return value

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value

class UserLogin(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("New password must be at least 8 characters")
        return value

    @field_validator("confirm_new_password")
    @classmethod
    def new_passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return value
