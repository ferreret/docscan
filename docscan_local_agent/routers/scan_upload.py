"""Endpoint POST /scan-and-upload — captura una página y la sube al SaaS.

Combina /scan + upload en una sola operación para evitar el doble
salto navegador → agente → navegador → SaaS. El agente sube
directamente al SaaS usando su ``agent_token``.

Flujo:
  1. Validar que el agente está paired (require_paired).
  2. Validar que ``scanner_name`` aparece en list_sources() → 404 si no.
  3. acquire(flatbed) → primera página.
  4. Encode PNG.
  5. POST {saas_url}/api/batches/{batch_id}/pages con el agent_token.
  6. Devolver el ``PageUploadResponse`` del SaaS.

Errores:
  - 401 sin pairing.
  - 404 scanner_name desconocido o batch ajeno (relayed del SaaS).
  - 401 si el SaaS rechaza el token (relayed).
  - 422 validación del body.
  - 500 acquire() falla, lista vacía, o encode PNG falla.
  - 502 SaaS inalcanzable.
  - 503 sin backends instalados.
"""

from __future__ import annotations

import logging
from typing import Literal

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.scanner_service import ScanConfig
from docscan_local_agent.credentials import AgentCredentials
from docscan_local_agent.deps import (
    SaasClientFactory,
    ScannerFactory,
    get_saas_client_factory,
    get_scanner_factory,
    require_paired,
)
from docscan_local_agent.saas_client import SaasUnavailable, UploadError

log = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

ScanMode = Literal["Color", "Gray", "Lineart"]


class ScanAndUploadRequest(BaseModel):
    """Body del POST /scan-and-upload."""

    scanner_name: str = Field(..., min_length=1)
    batch_id: int = Field(..., gt=0)
    resolution: int = Field(default=300, ge=72, le=1200)
    mode: ScanMode = Field(default="Color")


@router.post("/scan-and-upload", status_code=status.HTTP_201_CREATED)
def scan_and_upload(
    body: ScanAndUploadRequest,
    creds: AgentCredentials = Depends(require_paired),
    scanner_factory: ScannerFactory = Depends(get_scanner_factory),
    saas_factory: SaasClientFactory = Depends(get_saas_client_factory),
) -> dict:
    """Captura flatbed single-page y sube el PNG al lote del SaaS."""
    try:
        scanner = scanner_factory()
    except RuntimeError as exc:
        log.warning("Sin backends de escáner: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No hay backends de escáner disponibles: {exc}",
        ) from exc

    png_bytes: bytes
    try:
        sources = scanner.list_sources()
        if body.scanner_name not in sources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Escáner no existe: {body.scanner_name!r}",
            )

        config = ScanConfig(
            resolution=body.resolution,
            mode=body.mode,
            source_type="flatbed",
        )
        try:
            images = scanner.acquire(body.scanner_name, config)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("acquire() falló para %s", body.scanner_name)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error de captura: {exc}",
            ) from exc

        if not images:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El escáner no devolvió ninguna página",
            )

        png_bytes = _encode_png(images[0])
    finally:
        try:
            scanner.close()
        except Exception:
            log.warning("close() del scanner falló (best-effort)", exc_info=True)

    # Subir al SaaS con el agent_token persistido en agent.json.
    with saas_factory(creds.saas_url) as saas:
        try:
            return saas.upload_page(
                batch_id=body.batch_id,
                agent_token=creds.agent_token,
                png_bytes=png_bytes,
            )
        except UploadError as exc:
            # Relayed: el SaaS sabe mejor por qué (404 batch ajeno, 401
            # token revocado, 409 batch en ejecución, etc.).
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except SaasUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SaaS inalcanzable: {exc}",
            ) from exc


def _encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo codificar la imagen como PNG",
        )
    return bytes(buf)
