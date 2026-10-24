from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["superadmin", "admin", "manager"]
StoredRole = Literal["admin", "manager"]  # роли, которые хранятся в БД; суперадмин живёт в .env


class UserLogin(BaseModel):
    login: str
    password: str


class CurrentUser(BaseModel):
    login: str
    role: Role
    email: str | None = None
    # id аккаунта для токена (superadmin — для админа из .env); наружу не отдаётся
    uid: str | None = Field(default=None, exclude=True)
