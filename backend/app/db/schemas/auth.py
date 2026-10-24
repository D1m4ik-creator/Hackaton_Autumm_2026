from typing import Literal

from pydantic import BaseModel

Role = Literal["admin", "manager"]


class UserLogin(BaseModel):
    login: str
    password: str


class CurrentUser(BaseModel):
    login: str
    role: Role
    email: str | None = None
