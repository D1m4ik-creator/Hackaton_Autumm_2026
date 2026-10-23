from .base import Base
from .sessions import AuthSession

# Новые модели импортировать сюда, чтобы Alembic их видел

__all__ = ["Base", "AuthSession"]
