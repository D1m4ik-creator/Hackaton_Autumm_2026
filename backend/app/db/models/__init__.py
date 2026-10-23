from .base import Base
from .users import User

# Новые модели импортировать сюда, чтобы Alembic их видел

__all__ = ["Base", "User"]
