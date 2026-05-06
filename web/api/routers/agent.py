"""Router ``/api/agent/*`` — pairing y heartbeat de agentes locales.

Endpoints expuestos:

- ``POST /api/agent/pair-init``    (Bearer JWT user) — genera código de
  pairing.
- ``POST /api/agent/pair-claim``   (público) — el agente reclama el código
  y obtiene su ``agent_token`` long-lived.
- ``GET  /api/agent/whoami``       (Bearer agent_token) — info del
  dispositivo + user + tenant.
- ``POST /api/agent/heartbeat``    (Bearer agent_token) — actualiza
  ``last_seen``.

Sprint cliente local web, hito 3.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, HTTPException, status

from web.api.auth.dependencies import CurrentAgent, CurrentUser
from web.api.database import SessionDep
from web.api.models import AgentDevice
from web.api.schemas.agent import (
    AgentInfo,
    AgentTenantInfo,
    AgentUserInfo,
    HeartbeatResponse,
    PairClaimRequest,
    PairClaimResponse,
    PairInitRequest,
    PairInitResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


# Caracteres usados en el pairing code: mayúsculas + dígitos sin
# ambigüedad (sin O/0/I/1) para evitar errores de transcripción al
# leer en voz alta o copiar a mano.
_PAIR_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_PAIR_CODE_LENGTH = 8
_PAIR_CODE_TTL_MINUTES = 5

_AGENT_TOKEN_BYTES = 32  # → 64 chars hex


def _generate_pair_code() -> str:
    """Genera un código alfanumérico de 8 caracteres (sin ambigüedades)."""
    return "".join(
        secrets.choice(_PAIR_CODE_ALPHABET) for _ in range(_PAIR_CODE_LENGTH)
    )


def _generate_agent_secret() -> str:
    """Genera el secret del agent_token (parte tras el punto)."""
    return secrets.token_hex(_AGENT_TOKEN_BYTES)


def _hash_secret(secret: str) -> str:
    """Hashea el secret con bcrypt para almacenarlo en token_hash."""
    return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _now_utc_naive() -> datetime:
    """``datetime.utcnow()`` aislado para facilitar mocking en tests."""
    return datetime.utcnow()


# ----------------------------------------------------------------------
# POST /pair-init  (Bearer JWT user)
# ----------------------------------------------------------------------


@router.post(
    "/pair-init",
    response_model=PairInitResponse,
    status_code=status.HTTP_201_CREATED,
)
def pair_init(
    body: PairInitRequest,
    user: CurrentUser,
    db: SessionDep,
) -> PairInitResponse:
    """Inicia el pairing de un dispositivo nuevo.

    Crea un ``AgentDevice`` en estado pre-pairing con ``pairing_code``
    y ``code_expires_at`` (now + 5 min). El usuario verá el código en
    la UI y lo pegará en el agente local que llamará a ``/pair-claim``.
    """
    code = _generate_pair_code()
    expires_at = _now_utc_naive() + timedelta(minutes=_PAIR_CODE_TTL_MINUTES)

    device = AgentDevice(
        user_id=user.id,
        tenant_id=user.tenant_id,
        name=body.name,
        pairing_code=code,
        code_expires_at=expires_at,
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    log.info(
        "Pairing init: device_id=%s user_id=%s tenant_id=%s",
        device.id,
        user.id,
        user.tenant_id,
    )

    return PairInitResponse(
        device_id=device.id,
        code=code,
        expires_at=expires_at,
    )


# ----------------------------------------------------------------------
# POST /pair-claim  (público — el agente aún no tiene token)
# ----------------------------------------------------------------------


@router.post("/pair-claim", response_model=PairClaimResponse)
def pair_claim(
    body: PairClaimRequest,
    db: SessionDep,
) -> PairClaimResponse:
    """El agente reclama el código y obtiene su ``agent_token``.

    Errores:
      - 404 si el código no existe o ya fue consumido (token_hash != NULL)
      - 410 si el código expiró
    """
    code = body.code.strip().upper()

    # Buscar device con código pendiente.
    device = (
        db.query(AgentDevice).filter(AgentDevice.pairing_code == code).one_or_none()
    )

    if device is None:
        # Cubre tanto código inexistente como ya reclamado (pairing_code
        # se nullea tras el claim).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código de pairing no válido",
        )

    if device.code_expires_at is None or device.code_expires_at < _now_utc_naive():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Código de pairing expirado",
        )

    # Generar el agent_token y persistirlo.
    secret = _generate_agent_secret()
    device.token_hash = _hash_secret(secret)
    device.paired_at = _now_utc_naive()
    device.pairing_code = None
    device.code_expires_at = None
    db.commit()
    db.refresh(device)

    agent_token = f"{device.id}.{secret}"

    log.info(
        "Pairing claimed: device_id=%s user_id=%s tenant_id=%s",
        device.id,
        device.user_id,
        device.tenant_id,
    )

    return PairClaimResponse(
        agent_token=agent_token,
        device_id=device.id,
    )


# ----------------------------------------------------------------------
# GET /whoami  (Bearer agent_token)
# ----------------------------------------------------------------------


@router.get("/whoami", response_model=AgentInfo)
def whoami(agent: CurrentAgent, db: SessionDep) -> AgentInfo:
    """Devuelve info del dispositivo y de su user/tenant propietarios."""
    # Cargar user y tenant. El agent ya está validado por la dependency.
    from web.api.models import Tenant, User  # local import por brevedad

    user = db.get(User, agent.user_id)
    tenant = db.get(Tenant, agent.tenant_id)
    # Estos NO deberían ser None tras pasar la dependency; defensivos:
    if user is None or tenant is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Estado de agente inconsistente",
        )

    assert agent.paired_at is not None  # garantizado por la dependency

    return AgentInfo(
        device_id=agent.id,
        name=agent.name,
        user=AgentUserInfo(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
        ),
        tenant=AgentTenantInfo(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
        ),
        paired_at=agent.paired_at,
        last_seen=agent.last_seen,
    )


# ----------------------------------------------------------------------
# POST /heartbeat  (Bearer agent_token)
# ----------------------------------------------------------------------


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(agent: CurrentAgent, db: SessionDep) -> HeartbeatResponse:
    """Actualiza ``last_seen`` del agente. Útil para detectar agentes caídos."""
    now = _now_utc_naive()
    agent.last_seen = now
    db.commit()
    return HeartbeatResponse(last_seen=now)
