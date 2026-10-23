from pydantic import BaseModel


class UserLogin(BaseModel):
    login: str
    password: str


class CurrentUser(BaseModel):
    login: str
