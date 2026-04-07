"""Router de autenticación: login, registro, perfil."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from web.api.auth.dependencies import CurrentUser
from web.api.auth.security import create_access_token, hash_password, verify_password
from web.api.database import SessionDep
from web.api.models import ROLE_COMPANY_ADMIN, Tenant, User
from web.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


def _slugify(name: str) -> str:
    """Convierte un nombre a slug URL-safe."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, db: SessionDep):
    """Registra un nuevo tenant con su usuario administrador."""
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    slug = _slugify(data.tenant_name)
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
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=ROLE_COMPANY_ADMIN,
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


def _authenticate(email: str, password: str, db: SessionDep) -> TokenResponse:
    """Lógica compartida de autenticación."""
    user = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": user.tenant_id,
            "role": user.role,
        }
    )
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: SessionDep):
    """Autentica usuario con JSON y devuelve JWT."""
    return _authenticate(data.email, data.password, db)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: SessionDep = None):
    """Endpoint OAuth2 form-data para Swagger Authorize."""
    return _authenticate(form.username, form.password, db)


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
