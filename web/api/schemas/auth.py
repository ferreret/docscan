"""Schemas Pydantic para autenticación."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    """Respuesta con token JWT."""

    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Datos de inicio de sesión."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Datos de registro de usuario y tenant."""

    email: EmailStr
    password: str
    display_name: str
    tenant_name: str


class UserResponse(BaseModel):
    """Datos públicos del usuario."""

    id: int
    email: str
    display_name: str
    role: str
    tenant_id: int
    tenant_name: str

    model_config = {"from_attributes": True}
