from app.dao.base import BaseDAO
from app.db.models.transaction import Transaction


class TransactionDAO(BaseDAO):
    model = Transaction
