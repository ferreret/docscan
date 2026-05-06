"""Schemas Pydantic para los endpoints ``/api/agent/*``.

Usados por el router ``agent.py`` (hito 3 sprint cliente local web).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PairInitRequest(BaseModel):
    """Body de POST /api/agent/pair-init."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nombre legible del dispositivo (ej. 'Portátil Ana').",
    )


class PairInitResponse(BaseModel):
    """Respuesta de POST /api/agent/pair-init.

    El usuario verá ``code`` en la UI y lo pegará en el agente local.
    El agente lo enviará en POST /api/agent/pair-claim para obtener
    su ``agent_token``.
    """

    device_id: int
    code: str
    expires_at: datetime


class PairClaimRequest(BaseModel):
    """Body de POST /api/agent/pair-claim (público)."""

    code: str = Field(
        ...,
        min_length=4,
        max_length=16,
        description="Código corto recibido en pair-init.",
    )


class PairClaimResponse(BaseModel):
    """Respuesta de POST /api/agent/pair-claim.

    El agente debe guardar ``agent_token`` de forma persistente.
    """

    agent_token: str
    device_id: int


class AgentUserInfo(BaseModel):
    """Datos del propietario del agente, devueltos en /whoami."""

    id: int
    email: str
    display_name: str
    role: str


class AgentTenantInfo(BaseModel):
    """Datos del tenant del agente, devueltos en /whoami."""

    id: int
    name: str
    slug: str


class AgentInfo(BaseModel):
    """Respuesta de GET /api/agent/whoami."""

    device_id: int
    name: str
    user: AgentUserInfo
    tenant: AgentTenantInfo
    paired_at: datetime
    last_seen: datetime | None


class HeartbeatResponse(BaseModel):
    """Respuesta de POST /api/agent/heartbeat."""

    last_seen: datetime
