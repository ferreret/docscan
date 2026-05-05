"""Schemas Pydantic para los endpoints administrativos del superadmin.

Usados por ``/api/admin/tenants`` y ``/api/admin/users`` (hitos 5 y 6
del sprint superadmin).
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_PLANS: tuple[str, ...] = ("free", "basic", "enterprise")


class TenantStats(BaseModel):
    """Estadísticas agregadas de un tenant."""

    n_users: int
    n_applications: int
    n_batches: int


class TenantListItem(BaseModel):
    """Tenant en listados/respuestas administrativas."""

    id: int
    name: str
    slug: str
    plan: str
    active: bool
    created_at: datetime
    stats: TenantStats


class TenantUserItem(BaseModel):
    """Usuario tal y como aparece en el detalle de un tenant."""

    id: int
    email: str
    display_name: str
    role: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantDetail(TenantListItem):
    """Tenant con la lista de sus usuarios."""

    users: list[TenantUserItem]


class TenantCreateRequest(BaseModel):
    """Payload para crear un tenant + su primer company_admin."""

    tenant_name: str = Field(min_length=1, max_length=200)
    plan: str = Field(default="free")
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    admin_display_name: str = Field(min_length=1, max_length=200)

    _ALLOWED_PLANS: ClassVar[tuple[str, ...]] = ALLOWED_PLANS

    @field_validator("plan")
    @classmethod
    def _check_plan(cls, v: str) -> str:
        if v not in ALLOWED_PLANS:
            raise ValueError(
                f"plan inválido. Debe ser uno de: {', '.join(ALLOWED_PLANS)}"
            )
        return v


class TenantUpdateRequest(BaseModel):
    """Cambios permitidos sobre un tenant."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    plan: str | None = None
    active: bool | None = None

    @field_validator("plan")
    @classmethod
    def _check_plan(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_PLANS:
            raise ValueError(
                f"plan inválido. Debe ser uno de: {', '.join(ALLOWED_PLANS)}"
            )
        return v


# --------------------------------------------------------------------
# Usuarios cross-tenant (gestión por superadmin)
# --------------------------------------------------------------------

ALLOWED_ADMIN_ROLES: tuple[str, ...] = ("superadmin", "company_admin", "operator")


class AdminUserListItem(BaseModel):
    """Usuario en respuestas administrativas (cross-tenant).

    Incluye ``tenant_id`` y ``tenant_name`` porque el superadmin opera
    sobre cualquier tenant.
    """

    id: int
    email: str
    display_name: str
    role: str
    active: bool
    created_at: datetime
    tenant_id: int
    tenant_name: str


class AdminUserCreateRequest(BaseModel):
    """Payload para crear un usuario directamente en cualquier tenant."""

    tenant_id: int
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=200)
    role: str

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        if v not in ALLOWED_ADMIN_ROLES:
            raise ValueError(
                f"rol inválido. Debe ser uno de: {', '.join(ALLOWED_ADMIN_ROLES)}"
            )
        return v


class AdminUserUpdateRequest(BaseModel):
    """Cambios permitidos sobre un usuario por el superadmin."""

    role: str | None = None
    active: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_ADMIN_ROLES:
            raise ValueError(
                f"rol inválido. Debe ser uno de: {', '.join(ALLOWED_ADMIN_ROLES)}"
            )
        return v
