"""Синхронизация пользователей панели в Authentik через его REST API (/api/v3).

Пользователь панели и пользователь Authentik связаны по username = логину панели.
Почта в Authentik та же, что в панели: по ней колбэк OIDC находит локальный
аккаунт (app/routers/oidc.py). Пароль передаётся открытым текстом только сюда,
в БД панели по-прежнему лежит лишь хэш.

Если синхронизация выключена (нет AUTHENTIK_API_URL/AUTHENTIK_API_TOKEN), все
функции ничего не делают.
"""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Папка пользователей панели в Authentik (Directory → Users), чтобы их было видно отдельно
USER_PATH = "aeza-panel"
TIMEOUT_SECONDS = 10


class AuthentikSyncError(Exception):
    """Authentik не ответил или вернул ошибку"""


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=f"{settings.authentik_api_url.rstrip('/')}/api/v3",
        headers={"Authorization": f"Bearer {settings.authentik_api_token.get_secret_value()}"},
        timeout=TIMEOUT_SECONDS,
    )


async def _call(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    try:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        # Текст ответа Authentik не логируем целиком: в теле запроса мог быть пароль
        status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        raise AuthentikSyncError(f"{method} {url}: {status_code or type(exc).__name__}") from exc
    return response


async def _find_pk(client: httpx.AsyncClient, username: str) -> int | None:
    response = await _call(client, "GET", "/core/users/", params={"username": username})
    results = response.json()["results"]
    return results[0]["pk"] if results else None


async def upsert_user(
    *, login: str, email: str, password: str | None = None, old_login: str | None = None
) -> int | None:
    """Создаёт или обновляет пользователя Authentik.

    Возвращает pk, если пользователь создан этим вызовом (его можно откатить через
    delete_user_by_pk), иначе None — обновлён существующий или синхронизация выключена.

    old_login — прежний логин при переименовании: по нему ищется существующий пользователь.
    Пользователь, которого в Authentik ещё нет (создан до включения синхронизации), создаётся;
    без пароля он войти в Authentik не сможет, пока пароль не зададут в панели.
    """
    if not get_settings().authentik_sync_enabled:
        return None
    body = {"username": login, "name": login, "email": email, "is_active": True, "path": USER_PATH}
    async with _client() as client:
        pk = await _find_pk(client, old_login or login)
        if pk is None and old_login:
            pk = await _find_pk(client, login)
        created = pk is None
        if created:
            pk = (await _call(client, "POST", "/core/users/", json=body)).json()["pk"]
        else:
            await _call(client, "PATCH", f"/core/users/{pk}/", json=body)
        if password is not None:
            try:
                await _call(client, "POST", f"/core/users/{pk}/set_password/", json={"password": password})
            except AuthentikSyncError:
                if created:
                    await _call(client, "DELETE", f"/core/users/{pk}/")
                raise
    return pk if created else None


async def delete_user(login: str) -> None:
    """Удаляет пользователя Authentik по логину; ошибки только логируются (панель уже удалила аккаунт)"""
    if not get_settings().authentik_sync_enabled:
        return
    try:
        async with _client() as client:
            pk = await _find_pk(client, login)
            if pk is not None:
                await _call(client, "DELETE", f"/core/users/{pk}/")
    except AuthentikSyncError:
        # Без аккаунта в панели вход через Authentik всё равно вернёт oidc_no_account
        logger.exception("Не удалось удалить пользователя %s в Authentik", login)


async def delete_user_by_pk(pk: int) -> None:
    """Откат создания: удаляет только что созданного пользователя Authentik, ошибки логируются"""
    try:
        async with _client() as client:
            await _call(client, "DELETE", f"/core/users/{pk}/")
    except AuthentikSyncError:
        logger.exception("Не удалось откатить создание пользователя Authentik pk=%s", pk)
