"""Endpoint POST /pair — el frontend pega el código y el agente lo canjea.

Flujo:

1. El usuario en la web hace ``POST /api/agent/pair-init`` (con su JWT) y
   obtiene un código corto.
2. El usuario abre ``http://localhost:47816`` (el agente) y pega el código
   junto con la URL del SaaS.
3. Este endpoint llama a ``pair-claim`` para obtener el ``agent_token``,
   luego a ``whoami`` para resolver email/tenant, y persiste todo en
   ``~/.docscan/agent.json``.

El ``agent_token`` NUNCA se devuelve al frontend — sólo metadatos
descriptivos. Si el agente ya está pareado responde 409 sin tocar el SaaS.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from docscan_local_agent.credentials import (
    AgentCredentials,
    load_credentials,
    save_credentials,
)
from docscan_local_agent.deps import (
    SaasClientFactory,
    get_saas_client_factory,
    get_settings,
)
from docscan_local_agent.saas_client import (
    PairClaimError,
    SaasUnavailable,
    WhoamiError,
)
from docscan_local_agent.settings import AgentSettings

log = logging.getLogger(__name__)

router = APIRouter(tags=["pair"])


class PairRequest(BaseModel):
    """Body del POST /pair."""

    saas_url: HttpUrl = Field(
        ..., description="URL base del SaaS (ej. https://docscan.example.com)"
    )
    code: str = Field(..., min_length=1, max_length=16)


class PairResponse(BaseModel):
    """Respuesta de POST /pair (sin el agent_token)."""

    paired: bool = True
    device_id: int
    device_name: str
    user_email: str
    tenant_name: str
    paired_at: datetime


@router.post("/pair", response_model=PairResponse)
def pair(
    body: PairRequest,
    settings: AgentSettings = Depends(get_settings),
    saas_factory: SaasClientFactory = Depends(get_saas_client_factory),
) -> PairResponse:
    """Empareja el agente con el SaaS canjeando un código corto.

    Errores:
      - 409 si ya hay credenciales válidas en disco.
      - 404/410 (relayed) si el SaaS rechaza el código (no válido / expirado).
      - 502 si el SaaS no responde.
    """
    if load_credentials(settings.config_dir) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El agente ya está emparejado.",
        )

    base_url = str(body.saas_url).rstrip("/")

    with saas_factory(base_url) as saas:
        try:
            claim = saas.pair_claim(body.code)
        except PairClaimError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except SaasUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SaaS inalcanzable: {exc}",
            ) from exc

        try:
            info = saas.whoami(claim.agent_token)
        except WhoamiError as exc:
            log.error(
                "whoami falló justo tras pair-claim (device_id=%s, status=%s, detail=%s)",
                claim.device_id,
                exc.status_code,
                exc.detail,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SaaS rechazó el token recién emitido: {exc.detail}",
            ) from exc
        except SaasUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SaaS inalcanzable: {exc}",
            ) from exc

    creds = AgentCredentials(
        saas_url=base_url,
        agent_token=claim.agent_token,
        device_id=info.device_id,
        device_name=info.name,
        user_email=info.user.email,
        tenant_name=info.tenant.name,
        paired_at=info.paired_at,
    )
    save_credentials(creds, settings.config_dir)

    log.info(
        "Agent paired: device_id=%s tenant=%s user=%s",
        info.device_id,
        info.tenant.name,
        info.user.email,
    )

    return PairResponse(
        device_id=info.device_id,
        device_name=info.name,
        user_email=info.user.email,
        tenant_name=info.tenant.name,
        paired_at=info.paired_at,
    )
