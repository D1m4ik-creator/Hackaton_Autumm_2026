"""Ограничение подбора пароля по конкретному логину.

Дополняет лимит по IP (slowapi): даже при смене адреса перебор пароля для
одного логина упирается в отдельный счётчик неудачных входов. Счётчики лежат
в памяти процесса и защищены asyncio.Lock (работаем в одном event loop).
Отключается вместе с rate_limit_enabled.
"""

import math
import time
from asyncio import Lock
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class _Attempts:
    count: int
    first_at: float


class LoginGuard:
    """Счётчик неудачных входов по нормализованному логину с окном и лимитом."""

    def __init__(
        self,
        *,
        max_failures: int | None = None,
        window_seconds: int | None = None,
        enabled: bool | None = None,
        max_keys: int = 10_000,
        now=time.monotonic,
    ) -> None:
        # None означает «брать из настроек»; явные значения удобны в тестах
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._enabled = enabled
        self._max_keys = max_keys
        self._now = now
        self._attempts: dict[str, _Attempts] = {}
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        if self._enabled is not None:
            return self._enabled
        return get_settings().rate_limit_enabled

    @property
    def max_failures(self) -> int:
        if self._max_failures is not None:
            return self._max_failures
        return get_settings().login_max_failures

    @property
    def window_seconds(self) -> int:
        if self._window_seconds is not None:
            return self._window_seconds
        return get_settings().login_failure_window_seconds

    @staticmethod
    def _normalize(login: str) -> str:
        """Один ключ на логин: регистр и длинный хвост не создают новых записей"""
        return login.lower()[:100]

    def _purge_expired(self, now: float) -> None:
        """Чистит просроченные записи; если ключей всё равно слишком много — самые старые"""
        window = self.window_seconds
        expired = [key for key, item in self._attempts.items() if now - item.first_at >= window]
        for key in expired:
            del self._attempts[key]
        if len(self._attempts) > self._max_keys:
            # Оставляем только самые свежие max_keys записей
            for key in sorted(self._attempts, key=lambda k: self._attempts[k].first_at)[
                : len(self._attempts) - self._max_keys
            ]:
                del self._attempts[key]

    async def retry_after(self, login: str) -> int | None:
        """Сколько секунд логин заблокирован, или None, если вход разрешён"""
        if not self.enabled:
            return None
        key = self._normalize(login)
        now = self._now()
        async with self._lock:
            item = self._attempts.get(key)
            if item is None:
                return None
            if now - item.first_at >= self.window_seconds:
                del self._attempts[key]
                return None
            if item.count >= self.max_failures:
                return max(1, math.ceil(self.window_seconds - (now - item.first_at)))
            return None

    async def record_failure(self, login: str) -> None:
        """Отмечает неудачный вход; новое окно начинается с первой неудачи"""
        if not self.enabled:
            return
        key = self._normalize(login)
        now = self._now()
        async with self._lock:
            item = self._attempts.get(key)
            if item is None or now - item.first_at >= self.window_seconds:
                self._attempts[key] = _Attempts(count=1, first_at=now)
            else:
                item.count += 1
            self._purge_expired(now)

    async def record_success(self, login: str) -> None:
        """Успешный вход сбрасывает счётчик логина"""
        if not self.enabled:
            return
        key = self._normalize(login)
        async with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        """Сбрасывает все счётчики (используется в тестах)"""
        self._attempts.clear()


# Единый счётчик на процесс; параметры берутся из настроек
login_guard = LoginGuard()
