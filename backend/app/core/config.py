import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class DatabaseConfig(BaseModel):
    user: str
    password: SecretStr
    db: str
    host: str
    port: int
    echo: bool = False
    ssl: bool = False

    def get_db_url(self) -> str:
        encoded_password = quote_plus(self.password.get_secret_value())
        url = f"postgresql+asyncpg://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.db}"
        return f"{url}?ssl=require" if self.ssl else url


class JWTConfig(BaseModel):
    secret_key: SecretStr
    refresh_secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_grace_seconds: int = 30


class AdminConfig(BaseModel):
    login: str
    password: SecretStr


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        # Какой env-файл читать: по умолчанию .env (локальная база), ENV_FILE=.env.shared для общей
        env_file=str(ROOT_DIR / os.getenv("ENV_FILE", ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432
    postgres_ssl: bool = False

    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_refresh_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    # Сколько секунд после замены старый refresh ещё принимается (параллельные запросы из одного браузера)
    jwt_refresh_grace_seconds: int = 30

    # True на деплое с HTTPS: cookie уходят только по защищённому соединению
    cookie_secure: bool = False

    # Единственная учётная запись для входа в панель
    admin_login: str
    admin_password: SecretStr = Field(min_length=8)

    database_echo: bool = False

    # Список origin'ов фронта через запятую
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Путь к файлу исходного снимка для первичной загрузки в пустую базу
    source_data_path: Path = ROOT_DIR.parent / "origin_data" / "data.json"
    # Грузить снимок при старте, если таблица accounts пуста
    seed_on_startup: bool = True
    # Интервал опроса версии сводки в SSE-потоке, секунды
    sse_poll_interval_seconds: int = 1

    @property
    def database(self) -> DatabaseConfig:
        return DatabaseConfig(
            user=self.postgres_user,
            password=self.postgres_password,
            db=self.postgres_db,
            host=self.postgres_host,
            port=self.postgres_port,
            echo=self.database_echo,
            ssl=self.postgres_ssl,
        )

    @property
    def jwt(self) -> JWTConfig:
        return JWTConfig(
            secret_key=self.jwt_secret_key,
            refresh_secret_key=self.jwt_refresh_secret_key,
            algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.jwt_access_token_expire_minutes,
            refresh_token_expire_days=self.jwt_refresh_token_expire_days,
            refresh_grace_seconds=self.jwt_refresh_grace_seconds,
        )

    @property
    def admin(self) -> AdminConfig:
        return AdminConfig(login=self.admin_login, password=self.admin_password)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Config:
    return Config()
