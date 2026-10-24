from typing import Literal

from pydantic import BaseModel

Role = Literal["superadmin", "admin", "manager"]
StoredRole = Literal["admin", "manager"]  # роли, которые хранятся в БД; суперадмин живёт в .env


class UserLogin(BaseModel):
    login: str
    password: str


class CurrentUser(BaseModel):
    login: str
    role: Role
    email: str | None = None
