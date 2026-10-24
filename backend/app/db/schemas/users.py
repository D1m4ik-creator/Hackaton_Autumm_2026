import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from .auth import Role
from .common import CamelModel

LOGIN_PATTERN = r"^[A-Za-z0-9_.-]+$"


class UserCreate(CamelModel):
    login: str = Field(min_length=3, max_length=50, pattern=LOGIN_PATTERN)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()


class UserUpdate(CamelModel):
    login: str | None = Field(default=None, min_length=3, max_length=50, pattern=LOGIN_PATTERN)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value


class UserOut(CamelModel):
    id: uuid.UUID
    login: str
    email: str
    role: Role
    created_at: datetime
