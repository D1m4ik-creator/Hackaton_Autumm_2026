"""Тесты ограничения подбора пароля по конкретному логину (app.core.login_guard).

Юнит-тесты гоняют LoginGuard с явными параметрами (счётчики в памяти),
один интеграционный тест проверяет ответ 429 ручки /auth/login и то, что
верный пароль после блокировки тоже отвергается до истечения окна.
"""

from httpx import AsyncClient

from app.core.login_guard import LoginGuard, login_guard
from app.core.security import ACCESS_COOKIE

ADMIN = {"login": "admin", "password": "test_password"}


def _guard(**overrides) -> LoginGuard:
    params = {"enabled": True, "max_failures": 3, "window_seconds": 900}
    params.update(overrides)
    return LoginGuard(**params)


async def test_blocks_after_max_failures():
    guard = _guard()
    for _ in range(3):
        assert await guard.retry_after("user") is None
        await guard.record_failure("user")
    retry = await guard.retry_after("user")
    assert retry is not None and retry > 0


async def test_success_resets_counter():
    guard = _guard()
    await guard.record_failure("user")
    await guard.record_failure("user")
    await guard.record_success("user")
    assert await guard.retry_after("user") is None
    # После сброса снова нужно max_failures неудач, чтобы заблокировать
    await guard.record_failure("user")
    await guard.record_failure("user")
    assert await guard.retry_after("user") is None
    await guard.record_failure("user")
    assert await guard.retry_after("user") is not None


async def test_still_blocked_within_window():
    """Блокировка держится всё окно: верный пароль в роутере упрётся в retry_after раньше аутентификации."""
    guard = _guard()
    for _ in range(3):
        await guard.record_failure("user")
    assert await guard.retry_after("user") is not None
    # Повторная проверка (эмулирует запрос с верным паролем) всё ещё блокирует
    assert await guard.retry_after("user") is not None


async def test_block_expires_after_window():
    clock = [1000.0]
    guard = _guard(window_seconds=60, now=lambda: clock[0])
    for _ in range(3):
        await guard.record_failure("user")
    assert await guard.retry_after("user") is not None
    clock[0] += 61
    assert await guard.retry_after("user") is None


async def test_unknown_login_counted_like_known():
    """Несуществующий логин считается так же — без утечки существования."""
    guard = _guard()
    for _ in range(3):
        await guard.record_failure("ghost-user")
    assert await guard.retry_after("ghost-user") is not None


async def test_normalization_case_insensitive():
    guard = _guard()
    for _ in range(3):
        await guard.record_failure("USER")
    assert await guard.retry_after("user") is not None


async def test_disabled_guard_never_blocks():
    guard = _guard(enabled=False)
    for _ in range(10):
        await guard.record_failure("user")
    assert await guard.retry_after("user") is None


async def test_memory_is_bounded():
    guard = _guard(max_keys=5)
    for i in range(50):
        await guard.record_failure(f"user-{i}")
    assert len(guard._attempts) <= 5


async def test_login_endpoint_blocks_and_rejects_correct_password(client: AsyncClient):
    """Ручка /auth/login: после серии неудач 429 с Retry-After, верный пароль тоже 429 до истечения окна."""
    login_guard._enabled = True
    login_guard._max_failures = 3
    login_guard._window_seconds = 900
    login_guard.reset()
    try:
        for _ in range(3):
            wrong = await client.post("/api/v1/auth/login", json={"login": "admin", "password": "wrong-pass"})
            assert wrong.status_code == 401

        blocked = await client.post("/api/v1/auth/login", json={"login": "admin", "password": "wrong-pass"})
        assert blocked.status_code == 429
        assert blocked.headers.get("Retry-After")
        assert not client.cookies.get(ACCESS_COOKIE)

        # Верный пароль пока тоже отвергается: проверка блокировки идёт до аутентификации
        correct = await client.post("/api/v1/auth/login", json=ADMIN)
        assert correct.status_code == 429
        assert not client.cookies.get(ACCESS_COOKIE)
    finally:
        login_guard._enabled = None
        login_guard._max_failures = None
        login_guard._window_seconds = None
        login_guard.reset()


async def test_login_endpoint_success_resets_block(client: AsyncClient):
    """Неудачи ниже порога не мешают верному входу, и счётчик обнуляется после успеха."""
    login_guard._enabled = True
    login_guard._max_failures = 3
    login_guard._window_seconds = 900
    login_guard.reset()
    try:
        for _ in range(2):
            assert (
                await client.post("/api/v1/auth/login", json={"login": "admin", "password": "wrong-pass"})
            ).status_code == 401
        # Верный вход проходит и сбрасывает счётчик
        assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    finally:
        login_guard._enabled = None
        login_guard._max_failures = None
        login_guard._window_seconds = None
        login_guard.reset()
