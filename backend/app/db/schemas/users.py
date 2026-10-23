import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,64}$")


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: EmailStr
    created_at: datetime


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if not PASSWORD_RE.match(value):
            raise ValueError("Пароль должен быть от 8 до 64 символов и содержать хотя бы одну заглавную букву, одну строчную букву, одну цифру и один специальный символ.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
