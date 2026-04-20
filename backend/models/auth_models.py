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

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class UserLogin(BaseModel):
    email: str
    password: str
