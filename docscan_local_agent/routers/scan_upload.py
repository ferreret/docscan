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
from typing import Any, Literal

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
    options: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Overrides dinámicos de opciones del dispositivo (resolution, "
            "mode, source, brightness, contrast, ...). Las claves se "
            "validan contra ``get_device_options(scanner_name)`` — sólo se "
            "aceptan opciones is_settable=True. Si está presente, los "
            "valores top-level (resolution/mode) son ignorados."
        ),
    )


def _validate_options_whitelist(
    scanner, scanner_name: str, options: dict[str, Any]
) -> None:
    """Valida que cada clave de ``options`` sea settable según el dispositivo.

    Llama a ``scanner.get_device_options(scanner_name)`` y compara las
    claves recibidas contra las que el driver expone como
    ``is_settable=True``. Cualquier clave fuera de esa whitelist
    dispara 422 — el agente no permite setear "cualquier cosa" aunque
    la api del scanner lo aceptase, para no abrir un vector de
    abuso desde una pestaña web maliciosa.
    """
    if not options:
        return

    raw = scanner.get_device_options(scanner_name)
    allowed: set[str] = set()
    for o in raw:
        # ``o`` puede ser dataclass DeviceOption (desktop) o dict (FakeScanner).
        get = (
            (lambda key: o.get(key))
            if isinstance(o, dict)
            else (lambda key: getattr(o, key, None))
        )
        if get("is_settable"):
            allowed.add(get("name"))

    invalid = sorted(set(options.keys()) - allowed)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Opciones desconocidas o no modificables para "
                f"{scanner_name!r}: {invalid}"
            ),
        )


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

        # Validar overrides contra la whitelist dinámica del dispositivo.
        # Un dict vacío o None salta la validación.
        _validate_options_whitelist(scanner, body.scanner_name, body.options or {})

        config = ScanConfig(
            resolution=body.resolution,
            mode=body.mode,
            source_type="flatbed",
            extra_options=dict(body.options) if body.options else {},
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
