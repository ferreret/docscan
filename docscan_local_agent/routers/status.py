"""Endpoint GET /status — heartbeat público del agente local.

Devuelve siempre 200 con un JSON describiendo el estado del agente:

- ``name``/``version``: identificación.
- ``paired``: ``True`` si hay credenciales válidas en ``~/.docscan/agent.json``.
- ``device_name``/``user_email``/``tenant_name``: metadatos descriptivos
  cuando ``paired=True`` (omitidos / null en pre-pairing).

NUNCA devuelve el ``agent_token`` — éste sólo se persiste en disco con
permisos 0600 y se usa internamente como ``Authorization: Bearer …``.

El frontend del SaaS llama a este endpoint para detectar si hay un
agente local arrancado en localhost, antes de mostrar la pantalla de
pairing o el panel "Mi estación".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from docscan_local_agent import __version__
from docscan_local_agent.credentials import load_credentials
from docscan_local_agent.deps import get_settings
from docscan_local_agent.settings import AgentSettings

router = APIRouter(tags=["status"])


class StatusResponse(BaseModel):
    """Estado público del agente."""

    name: str
    version: str
    paired: bool
    device_name: str | None = None
    user_email: str | None = None
    tenant_name: str | None = None


@router.get("/status", response_model=StatusResponse)
def get_status(
    settings: AgentSettings = Depends(get_settings),
) -> StatusResponse:
    """Devuelve nombre, versión y si el agente está vinculado a un usuario."""
    creds = load_credentials(settings.config_dir)
    if creds is None:
        return StatusResponse(
            name="docscan-local-agent", version=__version__, paired=False
        )

    return StatusResponse(
        name="docscan-local-agent",
        version=__version__,
        paired=True,
        device_name=creds.device_name,
        user_email=creds.user_email,
        tenant_name=creds.tenant_name,
    )
