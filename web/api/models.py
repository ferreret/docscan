"""Modelos ORM exclusivos de la API web (Tenant, User).

Heredan de la misma Base que los modelos de app/ para compartir
metadata y poder crear todas las tablas con un solo create_all().
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# Roles de usuario
ROLE_SUPERADMIN = "superadmin"
ROLE_COMPANY_ADMIN = "company_admin"
ROLE_OPERATOR = "operator"

VALID_ROLES = (ROLE_SUPERADMIN, ROLE_COMPANY_ADMIN, ROLE_OPERATOR)


class Tenant(Base):
    """Empresa/organización (tenant) en multi-tenancy."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    users: Mapped[list[User]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}')>"


class User(Base):
    """Usuario de la plataforma web."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(50), default="operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    tenant: Mapped[Tenant] = relationship(back_populates="users")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class Invitation(Base):
    """Invitación para que un usuario externo se una a un tenant.

    Se crea por un company_admin con email + rol, genera un token
    aleatorio que el admin comparte fuera de banda (email manual,
    chat, etc). Al aceptar, se crea un User en el tenant y la
    invitación queda marcada como consumida.
    """

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(50), default="operator")
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"
