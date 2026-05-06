"""Persistencia de credenciales del agente local en ``~/.docscan/agent.json``.

El fichero contiene el ``agent_token`` recibido de pair-claim más metadatos
descriptivos (URL del SaaS, email del usuario propietario, nombre del
tenant). Lo cargamos al arrancar para responder a ``GET /status`` con
``paired: true`` sin tener que pegar al SaaS, y para autenticar las
llamadas posteriores al SaaS con ``Authorization: Bearer agent_token``.

Diseño:

- Pydantic ``AgentCredentials`` modela el JSON.
- Escritura atómica (tmp + ``os.replace``) para no dejar el fichero a
  medias si el proceso muere a mitad de write.
- En POSIX se aplica modo ``0o600`` (lectura/escritura sólo para el
  dueño): el ``agent_token`` es una credencial long-lived y no debe ser
  legible por otros usuarios del PC.
- Si el JSON está corrupto o no cumple el schema, ``load_credentials``
  devuelve ``None`` (estado pre-pairing) en lugar de crashear.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

_FILENAME = "agent.json"


class AgentCredentials(BaseModel):
    """Credenciales del agente tras un pairing exitoso."""

    saas_url: str
    agent_token: str
    device_id: int
    device_name: str
    user_email: str
    tenant_name: str
    paired_at: datetime


def _credentials_path(config_dir: Path) -> Path:
    return config_dir / _FILENAME


def load_credentials(config_dir: Path) -> AgentCredentials | None:
    """Lee y valida ``agent.json`` del ``config_dir`` indicado.

    Returns:
        Credenciales válidas o ``None`` si el fichero no existe, está
        corrupto, o no cumple el schema.
    """
    path = _credentials_path(config_dir)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return AgentCredentials.model_validate_json(raw)
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        log.warning("agent.json inválido o ilegible (%s): %s", path, exc)
        return None


def save_credentials(creds: AgentCredentials, config_dir: Path) -> None:
    """Persiste credenciales de forma atómica.

    Crea ``config_dir`` si no existe. Escribe primero a un tmp y luego
    ``os.replace`` para que un fallo a media escritura no deje el JSON
    corrupto.

    En POSIX aplica permisos ``0o600`` al fichero final.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    target = _credentials_path(config_dir)

    payload = creds.model_dump_json()

    fd, tmp_name = tempfile.mkstemp(
        prefix=".agent-", suffix=".json.tmp", dir=str(config_dir)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        if sys.platform != "win32":
            os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, target)
    except Exception:
        # Si algo falla, intentamos limpiar el tmp para no acumular basura.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def clear_credentials(config_dir: Path) -> None:
    """Borra ``agent.json`` si existe (idempotente)."""
    path = _credentials_path(config_dir)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("No se pudo borrar %s: %s", path, exc)
