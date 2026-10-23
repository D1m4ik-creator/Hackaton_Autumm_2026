"""Юнит-тесты для app.core.security: выпуск и проверка JWT, хэши, cookie."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.security import (
    ACCESS_COOKIE,
    ACCESS_TOKEN_TYPE,
    REFRESH_COOKIE,
    REFRESH_TOKEN_TYPE,
    access_decode_token,
    create_access_token,
    create_refresh_token,
    get_session_id,
    get_token,
    hash_token,
    refresh_decode_token,
    verify_credentials,
)


def test_access_token_roundtrip():
    """Access токен декодируется обратно и несёт sub, type и срок жизни в будущем."""
    token = create_access_token({"sub": "admin"})
    payload = access_decode_token(token)

    assert payload["sub"] == "admin"
    assert payload["type"] == ACCESS_TOKEN_TYPE
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_refresh_token_roundtrip_with_session_id():
    """Refresh токен декодируется и содержит id сессии (sid)."""
    sid = uuid.uuid4()
    token = create_refresh_token({"sub": "admin", "sid": str(sid)})
    payload = refresh_decode_token(token)

    assert payload["type"] == REFRESH_TOKEN_TYPE
    assert get_session_id(payload) == sid


def test_tokens_are_unique_even_for_same_payload():
    """jti делает токены уникальными, даже если выданы в одну секунду."""
    assert create_access_token({"sub": "admin"}) != create_access_token({"sub": "admin"})


def test_access_token_rejected_as_refresh():
    """Токен типа access не проходит проверку типа refresh."""
    token = create_access_token({"sub": "admin"})
    with pytest.raises(HTTPException) as exc_info:
        refresh_decode_token(token)
    assert exc_info.value.status_code == 401


def test_refresh_token_rejected_as_access():
    """Токен типа refresh не проходит проверку типа access."""
    token = create_refresh_token({"sub": "admin", "sid": str(uuid.uuid4())})
    with pytest.raises(HTTPException) as exc_info:
        access_decode_token(token)
    assert exc_info.value.status_code == 401


def test_tampered_token_rejected():
    """Изменённый токен не проходит проверку подписи."""
    token = create_access_token({"sub": "admin"})
    with pytest.raises(HTTPException) as exc_info:
        access_decode_token(token[:-1] + ("A" if token[-1] != "A" else "B"))
    assert exc_info.value.status_code == 401


def test_expired_access_token_rejected():
    """Просроченный токен отклоняется."""
    expired = jwt.encode(
        {
            "sub": "admin",
            "type": ACCESS_TOKEN_TYPE,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        get_settings().jwt.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        access_decode_token(expired)
    assert exc_info.value.status_code == 401


def test_refresh_decode_token_without_token():
    """Отсутствующий refresh токен — 401 с понятным текстом."""
    with pytest.raises(HTTPException) as exc_info:
        refresh_decode_token(None)
    assert exc_info.value.status_code == 401
    assert "не найден" in exc_info.value.detail


def test_get_session_id_rejects_bad_payload():
    """sid, который не UUID, или его отсутствие — 401."""
    with pytest.raises(HTTPException):
        get_session_id({"sid": "not-a-uuid"})
    with pytest.raises(HTTPException):
        get_session_id({})


def test_hash_token_is_sha256():
    token = "some-token-value"
    assert hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    # Детерминированно и различается для разных токенов
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token("other")


def test_verify_credentials():
    assert verify_credentials("admin", "test_password") is True
    assert verify_credentials("admin", "wrong_password") is False
    assert verify_credentials("not_admin", "test_password") is False


def _request_with_cookie(cookie: str | None) -> Request:
    headers = [(b"cookie", cookie.encode())] if cookie else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_get_token_from_cookie():
    request = _request_with_cookie(f"{ACCESS_COOKIE}=token-value; {REFRESH_COOKIE}=other")
    assert get_token(request) == "token-value"


def test_get_token_without_cookie():
    with pytest.raises(HTTPException) as exc_info:
        get_token(_request_with_cookie(None))
    assert exc_info.value.status_code == 401
    assert "не найден" in exc_info.value.detail
