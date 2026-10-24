from app.dao.base import BaseDAO
from app.db.models.service import Service


class ServiceDAO(BaseDAO):
    model = Service
