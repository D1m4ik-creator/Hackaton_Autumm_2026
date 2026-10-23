from fastapi import APIRouter, Depends

import app.crud.users as crud_user
from app.db.models.users import User as UserModel
from app.db.schemas.users import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/", response_model=User)
async def current_user(current_user: UserModel = Depends(crud_user.get_current_user)):
    return current_user
