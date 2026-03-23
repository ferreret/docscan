"""Configuración global de la aplicación con pydantic-settings.

Las variables se cargan en este orden de prioridad (mayor a menor):
1. Variables de entorno (prefijo DOCSCAN_)
2. Fichero .env (si existe)
3. Valores por defecto
"""

from __future__ import annotations

import platform
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

import platformdirs

# Directorio de datos de la aplicación (~/.local/share/docscan en Linux)
APP_DATA_DIR = Path(platformdirs.user_data_dir("docscan", appauthor=False))
APP_IMAGES_DIR = APP_DATA_DIR / "images"
APP_CONFIG_DIR = Path(platformdirs.user_config_dir("docscan", appauthor=False))


class DatabaseSettings(BaseModel):
    """Configuración de la base de datos."""

    path: Path = APP_DATA_DIR / "docscan.db"
    echo: bool = False  # Log SQL statements


class PipelineSettings(BaseModel):
    """Configuración del pipeline de procesado."""

    max_step_repeats: int = 3
    script_timeout_seconds: int = 30


class OcrSettings(BaseModel):
    """Configuración de motores OCR."""

    default_engine: str = "rapidocr"
    default_languages: list[str] = ["es"]
    models_dir: Path = APP_DATA_DIR / "ocr_models"


class ScannerSettings(BaseModel):
    """Configuración de escáner."""

    default_backend: str = "sane" if platform.system() == "Linux" else "twain"
    default_dpi: int = 300


class TransferSettings(BaseModel):
    """Configuración de transferencia."""

    collision_policy: str = "suffix"  # "suffix", "overwrite", "number"
    default_format: str = "tiff"


class Settings(BaseSettings):
    """Configuración global de DocScan Studio."""

    model_config = SettingsConfigDict(
        env_prefix="DOCSCAN_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = "DocScan Studio"
    debug: bool = False
    log_level: str = "INFO"

    # Subsistemas
    database: DatabaseSettings = DatabaseSettings()
    pipeline: PipelineSettings = PipelineSettings()
    ocr: OcrSettings = OcrSettings()
    scanner: ScannerSettings = ScannerSettings()
    transfer: TransferSettings = TransferSettings()

    # Secrets
    secrets_file: Path = APP_CONFIG_DIR / "secrets.enc"
    secrets_key_file: Path = APP_CONFIG_DIR / ".secrets.key"


def get_settings() -> Settings:
    """Carga y devuelve la configuración.

    Crea los directorios de datos y config si no existen.
    """
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
