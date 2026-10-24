from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Счётчики в памяти процесса, ключ — IP клиента; лимиты читаются из настроек при каждом запросе
limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)


def login_limit() -> str:
    return get_settings().rate_limit_login


def refresh_limit() -> str:
    return get_settings().rate_limit_refresh
