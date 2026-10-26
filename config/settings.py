"""Configuración global de la aplicación con pydantic-settings.

Las variables se cargan en este orden de prioridad (mayor a menor):
1. Variables de entorno (prefijo DOCSCAN_)
2. Fichero .env (si existe)
3. Valores por defecto
"""

from __future__ import annotations

import logging
import os
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


def ensure_private_dir(path: Path) -> None:
    """Crea ``path`` si no existe y lo deja legible solo por su usuario.

    Las imágenes de los lotes pueden contener datos personales (en hospitales,
    de pacientes). Con el umask por defecto (0755) cualquier otra cuenta del
    equipo podía leerlas. En POSIX se fija 0700; en Windows los permisos los
    gobierna la ACL del perfil del usuario y no se tocan.
    """
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            path.chmod(0o700)
        except OSError as e:
            logging.getLogger(__name__).warning(
                "No se pudieron restringir los permisos de %s: %s", path, e
            )


def get_settings() -> Settings:
    """Carga y devuelve la configuración.

    Crea los directorios de datos y config si no existen, privados al usuario.
    """
    ensure_private_dir(APP_DATA_DIR)
    ensure_private_dir(APP_CONFIG_DIR)
    return Settings()
