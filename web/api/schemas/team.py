"""Schemas para gestión de equipo: usuarios e invitaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserListItem(BaseModel):
    """Usuario del tenant (para listados de equipo)."""

    id: int
    email: str
    display_name: str
    role: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Cambios permitidos sobre un usuario del tenant."""

    role: str | None = None
    active: bool | None = None
    display_name: str | None = None


class InvitationCreate(BaseModel):
    """Payload para crear una invitación."""

    email: EmailStr
    role: str = Field(default="operator")


class InvitationResponse(BaseModel):
    """Invitación tal y como se devuelve al admin."""

    id: int
    email: str
    role: str
    token: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AcceptInvitationRequest(BaseModel):
    """Payload para aceptar una invitación (flujo público)."""

    token: str
    password: str = Field(min_length=8)
    display_name: str
