"""Schemas que modelan las respuestas del SaaS.

Replican lo mínimo de ``web/api/schemas/agent.py`` para que el agente
local NO arrastre el paquete web entero (que importa SQLAlchemy,
alembic, etc.) al empaquetarse con PyInstaller.

Si el contrato del SaaS cambia hay que sincronizarlos a mano. El test
de integración del Hito 4 (smoke contra el stack docker) pillará
divergencias en el schema antes de que lleguen a producción.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentUserInfo(BaseModel):
    id: int
    email: str
    display_name: str
    role: str


class AgentTenantInfo(BaseModel):
    id: int
    name: str
    slug: str


class AgentInfo(BaseModel):
    """Respuesta de ``GET /api/agent/whoami`` del SaaS."""

    device_id: int
    name: str
    user: AgentUserInfo
    tenant: AgentTenantInfo
    paired_at: datetime
    last_seen: datetime | None
