"""Router de autenticación: login, perfil.

El registro público fue eliminado: solo el superadmin de TecnoMedia
crea tenants. Ver ``web/api/bootstrap.py`` y los endpoints
``/api/admin/tenants``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from web.api.auth.dependencies import CurrentUser
from web.api.auth.security import create_access_token, verify_password
from web.api.database import SessionDep
from web.api.models import Tenant, User
from web.api.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


def _authenticate(email: str, password: str, db: Session) -> TokenResponse:
    """Lógica compartida de autenticación."""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

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

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant suspendido",
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
def login_form(db: SessionDep, form: OAuth2PasswordRequestForm = Depends()):
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
