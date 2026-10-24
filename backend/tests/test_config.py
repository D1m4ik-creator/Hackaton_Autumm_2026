"""Юнит-тесты для app.core.config: сборка конфигурации и URL подключения."""

import pytest
from pydantic import ValidationError

from app.core.config import Config


def _make_config(**overrides) -> Config:
    """Конфиг без чтения .env и переменных окружения: все поля задаём явно."""
    base = {
        "postgres_user": "user",
        "postgres_password": "secret",
        "postgres_db": "db",
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "jwt_secret_key": "a" * 32,
        "jwt_refresh_secret_key": "b" * 32,
        "admin_login": "admin",
        "admin_password": "password123",
        "session_secret_key": "c" * 32,
    }
    base.update(overrides)
    return Config(_env_file=None, **base)


def test_db_url_format():
    config = _make_config()
    assert config.database.get_db_url() == "postgresql+asyncpg://user:secret@localhost:5432/db"


def test_db_url_encodes_special_chars_in_password():
    """Пароль со спецсимволами URL-экранируется."""
    config = _make_config(postgres_password="p@ss w/ord")
    assert "p%40ss+w%2Ford" in config.database.get_db_url()


def test_cors_origins_list_parsing():
    """Запятые, пробелы и пустые элементы обрабатываются."""
    config = _make_config(cors_origins=" http://a , ,http://b ,")
    assert config.cors_origins_list == ["http://a", "http://b"]


def test_grouped_properties():
    config = _make_config()
    assert config.admin.login == "admin"
    assert config.admin.password.get_secret_value() == "password123"
    assert config.jwt.algorithm == "HS256"
    assert config.jwt.access_token_expire_minutes == 15
    assert config.database.echo is False


def test_short_jwt_secret_rejected():
    """JWT-секрет короче 32 символов не проходит валидацию."""
    with pytest.raises(ValidationError):
        _make_config(jwt_secret_key="too_short")


def test_short_admin_password_rejected():
    """Пароль администратора короче 8 символов не проходит валидацию."""
    with pytest.raises(ValidationError):
        _make_config(admin_password="short")
