"""Endpoint GET /status — heartbeat público del agente local."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from docscan_local_agent import __version__

router = APIRouter(tags=["status"])


class StatusResponse(BaseModel):
    """Estado público del agente."""

    name: str
    version: str
    paired: bool


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Devuelve nombre, versión y si el agente está vinculado a un usuario.

    Siempre disponible sin autenticación. El frontend lo usa para detectar
    si hay un agente local arrancado en localhost antes de mostrar la
    pantalla de pairing o el panel de "Mi estación".

    Note:
        ``paired`` se cableará al estado real del fichero ``agent.json``
        en el Hito 4. Por ahora hardcoded a ``False`` (esqueleto).
    """
    return StatusResponse(
        name="docscan-local-agent",
        version=__version__,
        paired=False,
    )
