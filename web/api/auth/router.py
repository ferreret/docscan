"""Router de autenticación: login, registro, perfil."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from web.api.auth.dependencies import CurrentUser
from web.api.auth.security import create_access_token, hash_password, verify_password
from web.api.database import SessionDep
from web.api.models import Tenant, User
from web.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, db: SessionDep):
    """Registra un nuevo tenant con su usuario administrador."""
    # Verificar email único
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    # Crear tenant
    slug = re.sub(r"[^a-z0-9]+", "-", data.tenant_name.lower()).strip("-")
    existing_tenant = db.execute(
        select(Tenant).where(Tenant.slug == slug)
    ).scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de organización ya existe",
        )

    tenant = Tenant(name=data.tenant_name, slug=slug)
    db.add(tenant)
    db.flush()  # Para obtener tenant.id

    # Crear usuario admin
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role="company_admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: SessionDep):
    """Autentica usuario y devuelve JWT."""
    user = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": user.tenant_id,
            "role": user.role,
        }
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_profile(user: CurrentUser, db: SessionDep):
    """Devuelve el perfil del usuario autenticado."""
    tenant = db.get(Tenant, user.tenant_id)
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant else "",
    )
