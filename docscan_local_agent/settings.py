"""Configuración del agente local.

Lee variables de entorno con prefijo ``DOCSCAN_AGENT_``. El usuario puede
sobreescribir cualquier setting exportando la variable correspondiente
antes de arrancar el proceso, por ejemplo::

    DOCSCAN_AGENT_PORT=50000 python -m docscan_local_agent
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Settings del agente local.

    Attributes:
        host: Interfaz de bind del servidor uvicorn. Por defecto sólo
            localhost para evitar exponer el agente fuera del PC.
        port: Puerto fijo. 47816 elegido por convención (configurable).
        config_dir: Directorio donde se guarda ``agent.json`` con el
            token de pairing. Por defecto ``~/.docscan``.
    """

    host: str = "127.0.0.1"
    port: int = 47816
    config_dir: Path = Path.home() / ".docscan"

    model_config = SettingsConfigDict(
        env_prefix="DOCSCAN_AGENT_",
        env_file=".env.agent",
        extra="ignore",
    )


def get_settings() -> AgentSettings:
    """Devuelve una instancia de settings.

    No la cacheamos para permitir que los tests sobreescriban variables
    de entorno entre invocaciones.
    """
    return AgentSettings()
