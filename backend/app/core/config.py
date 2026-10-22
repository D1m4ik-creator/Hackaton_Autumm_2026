import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import BaseModel, SecretStr
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

    database_echo: bool = False

    # Список origin'ов фронта через запятую
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

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
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Config:
    return Config()
