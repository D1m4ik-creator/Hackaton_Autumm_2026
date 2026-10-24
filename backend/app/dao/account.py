from app.dao.base import BaseDAO
from app.db.models.account import Account


class AccountDAO(BaseDAO):
    model = Account
