"""Configuración de la API web con pydantic-settings.

Variables con prefijo DOCSCAN_WEB_ o en fichero .env.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseWebSettings(BaseModel):
    """Conexión a PostgreSQL. Configurar via DOCSCAN_WEB_DATABASE__URL."""

    url: str = "postgresql+psycopg://user:pass@localhost:5432/docscan"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class JWTSettings(BaseModel):
    """Configuración JWT. Configurar via DOCSCAN_WEB_JWT__SECRET_KEY."""

    secret_key: str = ""  # Obligatorio: generar con `openssl rand -hex 32`
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7


class MinIOSettings(BaseModel):
    """Conexión a MinIO / S3. Configurar via DOCSCAN_WEB_MINIO__*."""

    endpoint: str = "localhost:9000"
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "docscan"
    use_ssl: bool = False


class RedisSettings(BaseModel):
    """Conexión a Redis."""

    url: str = "redis://localhost:6379/0"


class WebSettings(BaseSettings):
    """Configuración global de la API web."""

    model_config = SettingsConfigDict(
        env_prefix="DOCSCAN_WEB_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    debug: bool = False
    log_level: str = "INFO"
    deploy_mode: str = "onpremise"  # "onpremise" | "cloud"
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite dev server

    # Subsistemas
    database: DatabaseWebSettings = DatabaseWebSettings()
    jwt: JWTSettings = JWTSettings()
    minio: MinIOSettings = MinIOSettings()
    redis: RedisSettings = RedisSettings()


@lru_cache
def get_web_settings() -> WebSettings:
    """Carga y cachea la configuración web."""
    return WebSettings()
