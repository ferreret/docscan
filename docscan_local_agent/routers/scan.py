"""Endpoint POST /scan — captura una página y la devuelve como PNG.

Single-page flatbed por ahora. ADF (streaming multi-página) lo cubre el
hito 8. El cuerpo lleva sólo lo imprescindible (scanner_name +
resolution + mode); el agente delega 100% en
``app.services.scanner_service`` para no duplicar lógica.

La respuesta es ``image/png`` con los bytes crudos. Esto evita base64
(33 % overhead) y permite que el frontend del SaaS la trate como un
``Blob`` estándar.

Errores:
- 401 si el agente no está emparejado (vía require_paired).
- 404 si ``scanner_name`` no aparece en list_sources().
- 422 validación del body (Pydantic).
- 500 si la captura falla (paper jam, USB desconectado, etc.) o si
  acquire() devuelve lista vacía.
- 503 si el sistema no tiene backends de escáner instalados.
"""

from __future__ import annotations

import logging
from typing import Literal

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.scanner_service import ScanConfig
from docscan_local_agent.credentials import AgentCredentials
from docscan_local_agent.deps import (
    ScannerFactory,
    get_scanner_factory,
    require_paired,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

# Modos válidos según ScanConfig del desktop.
ScanMode = Literal["Color", "Gray", "Lineart"]


class ScanRequest(BaseModel):
    """Body del POST /scan."""

    scanner_name: str = Field(
        ..., min_length=1, description="Nombre devuelto por GET /scanners"
    )
    resolution: int = Field(
        default=300,
        ge=72,
        le=1200,
        description="DPI de captura (rango razonable para flatbed)",
    )
    mode: ScanMode = Field(default="Color", description="Color | Gray | Lineart")


@router.post("/scan", response_class=Response)
def scan(
    body: ScanRequest,
    _creds: AgentCredentials = Depends(require_paired),
    factory: ScannerFactory = Depends(get_scanner_factory),
) -> Response:
    """Captura una página single-page flatbed y devuelve el PNG."""
    try:
        scanner = factory()
    except RuntimeError as exc:
        log.warning("Sin backends de escáner: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No hay backends de escáner disponibles: {exc}",
        ) from exc

    try:
        # Validar que el scanner existe antes de intentar capturar — sino
        # el error del backend puede ser oscuro (timeout, segfault, ...).
        sources = scanner.list_sources()
        if body.scanner_name not in sources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Escáner no existe: {body.scanner_name!r}",
            )

        config = ScanConfig(
            resolution=body.resolution,
            mode=body.mode,
            source_type="flatbed",  # ADF en hito 8
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

    return Response(content=png_bytes, media_type="image/png")


def _encode_png(image: np.ndarray) -> bytes:
    """Codifica la imagen como PNG. Lanza HTTPException(500) si falla."""
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo codificar la imagen como PNG",
        )
    return bytes(buf)
