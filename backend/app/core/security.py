import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, status

from .config import get_settings

ACCESS_COOKIE = "users_access_token"
REFRESH_COOKIE = "users_refresh_token"

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def verify_credentials(login: str, password: str) -> bool:
    """Сверяет логин и пароль с учётной записью из .env (сравнение за постоянное время)"""
    admin = get_settings().admin
    login_ok = secrets.compare_digest(login.encode(), admin.login.encode())
    password_ok = secrets.compare_digest(password.encode(), admin.password.get_secret_value().encode())
    return login_ok and password_ok


def hash_token(token: str) -> str:
    """Хэш токена для хранения в БД (сам refresh токен в базе не лежит)"""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_token(data: dict, secret: str, expires_delta: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    to_encode.update(
        {
            "exp": datetime.now(timezone.utc) + expires_delta,
            "type": token_type,
            # jti делает каждый токен уникальным, даже если выдан в ту же секунду
            "jti": uuid.uuid4().hex,
        }
    )
    return jwt.encode(to_encode, secret, algorithm=get_settings().jwt.algorithm)


def create_access_token(data: dict) -> str:
    """Создание access токена"""
    jwt_settings = get_settings().jwt
    return _create_token(
        data,
        jwt_settings.secret_key.get_secret_value(),
        timedelta(minutes=jwt_settings.access_token_expire_minutes),
        ACCESS_TOKEN_TYPE,
    )


def create_refresh_token(data: dict) -> str:
    """Создание refresh токена"""
    jwt_settings = get_settings().jwt
    return _create_token(
        data,
        jwt_settings.refresh_secret_key.get_secret_value(),
        timedelta(days=jwt_settings.refresh_token_expire_days),
        REFRESH_TOKEN_TYPE,
    )


def _decode_token(token: str, secret: str, token_type: str, detail: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=[get_settings().jwt.algorithm])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    if payload.get("type") != token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    return payload


def access_decode_token(token: str) -> dict:
    """Декодирует access токен и возвращает его полезную нагрузку, если токен не валидный, то вызывает HTTPException с кодом 401"""
    return _decode_token(
        token,
        get_settings().jwt.secret_key.get_secret_value(),
        ACCESS_TOKEN_TYPE,
        "Токен не валидный!",
    )


def refresh_decode_token(token: str | None) -> dict:
    """Декодирует refresh токен, если токена нет или он не валидный, то вызывает HTTPException с кодом 401"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не найден")
    return _decode_token(
        token,
        get_settings().jwt.refresh_secret_key.get_secret_value(),
        REFRESH_TOKEN_TYPE,
        "Refresh token не валидный",
    )


def get_session_id(payload: dict) -> uuid.UUID:
    """Достаёт id сессии из payload refresh токена, если его нет или он битый, то вызывает HTTPException с кодом 401"""
    try:
        return uuid.UUID(payload.get("sid", ""))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не валидный")


def get_token(request: Request) -> str:
    """Получает access токен из cookie, если токен не найден, то вызывает HTTPException с кодом 401"""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен не найден")
    return token
