"""Dependencies de autenticación para FastAPI."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from web.api.auth.security import decode_access_token
from web.api.database import get_db
from web.api.models import AgentDevice, Tenant, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Obtiene el usuario actual a partir del JWT."""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario",
        )

    user = db.get(User, int(user_id))
    if user is None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant suspendido",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    """Dependency factory: exige que el usuario tenga uno de los roles indicados."""

    def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol requerido: {', '.join(roles)}",
            )
        return user

    return Depends(_check)


# --------------------------------------------------------------------
# Autenticación de agentes locales (sprint cliente local web)
# --------------------------------------------------------------------

# Formato del agent_token: "{agent_device_id}.{secret_hex}"
# El prefix permite buscar el AgentDevice en BD en O(1) y verificar
# bcrypt sólo del secret. Sin prefix tendríamos que comparar bcrypt
# contra todas las filas — O(N) prohibitivo.


def _parse_agent_token(token: str) -> tuple[int, str]:
    """Separa ``{device_id}.{secret}`` o lanza HTTPException 401."""
    if "." not in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente con formato inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    device_id_str, _, secret = token.partition(".")
    try:
        device_id = int(device_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente con formato inválido",
        ) from exc
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente con formato inválido",
        )
    return device_id, secret


def get_current_agent(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> AgentDevice:
    """Resuelve el header Bearer como ``agent_token`` de un AgentDevice.

    Falla con 401 si:
      - falta el header / formato distinto a "Bearer X"
      - el token no tiene formato ``{id}.{secret}``
      - el ``device_id`` no existe o está inactivo
      - el dispositivo aún no completó el pairing (token_hash NULL)
      - bcrypt verify falla
      - el tenant del agente está suspendido

    Nota: este endpoint NO acepta JWTs de usuario. Si quieres un
    endpoint que acepte ambos, usa la dependency híbrida que se
    introducirá en el hito 7.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization debe ser tipo Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer ") :]

    device_id, secret = _parse_agent_token(token)

    device = db.get(AgentDevice, device_id)
    if (
        device is None
        or not device.active
        or device.token_hash is None
        or device.paired_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agente no encontrado o no vinculado",
        )

    if not bcrypt.checkpw(secret.encode("utf-8"), device.token_hash.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente inválido",
        )

    tenant = db.get(Tenant, device.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant suspendido",
        )

    return device


CurrentAgent = Annotated[AgentDevice, Depends(get_current_agent)]


def _now_utc_naive() -> datetime:
    """Devuelve datetime UTC naive, para columnas DateTime sin timezone."""
    return datetime.utcnow()
