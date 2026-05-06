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


class AgentDevice(Base):
    """Dispositivo agente local vinculado a un usuario y tenant.

    El operario instala el agente local (``docscan_local_agent``) en su PC
    y lo empareja con su cuenta. Tras el pairing exitoso, el agente
    almacena un ``agent_token`` long-lived que usa para subir páginas
    escaneadas y recibir transferencias locales.

    Flujo de pairing:

    1. Usuario autenticado llama ``POST /api/agent/pair-init``: se crea
       un ``AgentDevice`` con ``pairing_code`` (8 chars) y
       ``code_expires_at`` (now + 5 min). ``token_hash`` y ``paired_at``
       quedan ``NULL`` hasta que se complete.
    2. El usuario pega el código en el agente local; el agente llama
       ``POST /api/agent/pair-claim`` (público) con el código y un
       nombre de dispositivo.
    3. El backend valida vigencia, genera ``agent_token`` (32 chars hex),
       guarda ``bcrypt(token)`` en ``token_hash``, marca ``paired_at``
       y nullea ``pairing_code``. Devuelve el token al agente.
    4. El agente persiste el token en ``~/.docscan/agent.json`` y lo
       envía como Bearer en peticiones posteriores.
    """

    __tablename__ = "agent_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))

    # Código corto para pairing inicial (NULL tras claim).
    pairing_code: Mapped[str | None] = mapped_column(
        String(16), unique=True, nullable=True, index=True
    )
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Hash bcrypt del agent_token (NULL antes del claim).
    token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<AgentDevice(id={self.id}, name='{self.name}', "
            f"user_id={self.user_id}, paired={self.paired_at is not None})>"
        )


class AuditLog(Base):
    """Registro de acciones administrativas para forensics y compliance.

    Lo escribe el helper :func:`web.api.audit.audit` desde los routers
    administrativos (``/api/admin/...``) y desde tareas internas. El
    ``actor_user_id`` es ``NULL`` para acciones de sistema (cron,
    recovery, etc.).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[int | None] = mapped_column(nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"target={self.target_type}:{self.target_id})>"
        )
