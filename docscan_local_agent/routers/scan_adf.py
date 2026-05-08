"""Endpoint POST /scan-adf-and-upload — captura todo el ADF y streamea NDJSON.

Hito 8 sprint cliente local web. A diferencia de /scan-and-upload (single
flatbed), aquí el agente:

  1. Itera ``scanner.acquire_iter`` con ``source_type="adf"``.
  2. Por cada página: encode PNG + upload al SaaS.
  3. Yield una línea NDJSON por evento (``started``, ``page_uploaded``,
     ``completed`` o ``error``).

El frontend consume el stream con ``fetch().body.getReader()`` para mostrar
progreso en tiempo real (típico ADF de oficina: 30-50 páginas, varios
minutos). Sin streaming el navegador percibiría un cuelgue.

El endpoint NO chequea ``is_disconnected``: las páginas ya capturadas
suben al SaaS aunque el cliente cierre la pestaña. Perder páginas físicas
del ADF sería peor UX que un cliente que no ve los últimos eventos.

Errores antes del stream (status code real):
- 401 sin pairing.
- 404 scanner_name desconocido.
- 422 validación del body.
- 503 sin backends de escáner instalados.

Errores durante el stream (status 200 + línea NDJSON ``error``):
- ``scan_error``: ``acquire_iter`` levantó (paper jam, USB desconectado, ...).
- ``upload_error``: el SaaS rechazó la subida (4xx/5xx, status_code incluido).
- ``saas_unavailable``: red al SaaS caída.
- ``encode_error``: cv2 no pudo codificar el PNG.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Literal

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
from docscan_local_agent.routers.scan_upload import _validate_options_whitelist
from docscan_local_agent.saas_client import SaasUnavailable, UploadError

log = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

ScanMode = Literal["Color", "Gray", "Lineart"]


class ScanAdfRequest(BaseModel):
    """Body del POST /scan-adf-and-upload."""

    scanner_name: str = Field(..., min_length=1)
    batch_id: int = Field(..., gt=0)
    resolution: int = Field(default=300, ge=72, le=1200)
    mode: ScanMode = Field(default="Color")
    options: dict | None = Field(
        default=None,
        description=(
            "Overrides dinámicos del dispositivo (resolution, mode, "
            "source, brightness, ...). Validados contra "
            "``get_device_options(scanner_name)`` con la misma whitelist "
            "que /scan-and-upload."
        ),
    )


def _ndjson(event: dict) -> bytes:
    """Serializa un evento como una línea NDJSON (UTF-8 + LF)."""
    return (json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8")


def _encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("No se pudo codificar la imagen como PNG")
    return bytes(buf)


@router.post("/scan-adf-and-upload")
def scan_adf_and_upload(
    body: ScanAdfRequest,
    creds: AgentCredentials = Depends(require_paired),
    scanner_factory: ScannerFactory = Depends(get_scanner_factory),
    saas_factory: SaasClientFactory = Depends(get_saas_client_factory),
) -> StreamingResponse:
    """Itera el ADF, sube página a página, devuelve NDJSON con progreso."""
    # Backend ausente: 503 antes del stream.
    try:
        scanner = scanner_factory()
    except RuntimeError as exc:
        log.warning("Sin backends de escáner: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No hay backends de escáner disponibles: {exc}",
        ) from exc

    # Validamos el scanner_name antes de abrir el stream para devolver un
    # 404 limpio (sin NDJSON). Si abriéramos el stream y dentro fallara el
    # acquire_iter, el frontend tendría que parsear NDJSON sólo para saber
    # que el escáner no existía.
    try:
        sources = scanner.list_sources()
    except Exception as exc:
        log.exception("list_sources falló")
        try:
            scanner.close()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudieron listar los escáneres: {exc}",
        ) from exc

    if body.scanner_name not in sources:
        try:
            scanner.close()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escáner no existe: {body.scanner_name!r}",
        )

    # Validar overrides contra la whitelist dinámica ANTES del stream:
    # un 422 sin NDJSON es mucho más fácil de manejar para el frontend
    # que parsear el primer evento del stream para descubrir el rechazo.
    try:
        _validate_options_whitelist(scanner, body.scanner_name, body.options or {})
    except HTTPException:
        try:
            scanner.close()
        except Exception:
            pass
        raise

    config = ScanConfig(
        resolution=body.resolution,
        mode=body.mode,
        source_type="adf",
        extra_options=dict(body.options) if body.options else {},
    )

    saas = saas_factory(creds.saas_url)

    def _stream() -> Iterator[bytes]:
        total = 0
        try:
            yield _ndjson({"event": "started"})

            try:
                pages = scanner.acquire_iter(body.scanner_name, config)
            except Exception as exc:
                log.exception("acquire_iter falló al iniciar")
                yield _ndjson(
                    {"event": "error", "code": "scan_error", "detail": str(exc)}
                )
                return

            for image in _safe_iter(pages):
                if isinstance(image, _ScanFailure):
                    log.warning("acquire_iter falló a media iteración: %s", image.exc)
                    yield _ndjson(
                        {
                            "event": "error",
                            "code": "scan_error",
                            "detail": str(image.exc),
                        }
                    )
                    return

                try:
                    png_bytes = _encode_png(image)
                except RuntimeError as exc:
                    yield _ndjson(
                        {
                            "event": "error",
                            "code": "encode_error",
                            "detail": str(exc),
                        }
                    )
                    return

                try:
                    result = saas.upload_page(
                        batch_id=body.batch_id,
                        agent_token=creds.agent_token,
                        png_bytes=png_bytes,
                    )
                except UploadError as exc:
                    yield _ndjson(
                        {
                            "event": "error",
                            "code": "upload_error",
                            "status_code": exc.status_code,
                            "detail": exc.detail,
                        }
                    )
                    return
                except SaasUnavailable as exc:
                    yield _ndjson(
                        {
                            "event": "error",
                            "code": "saas_unavailable",
                            "detail": str(exc),
                        }
                    )
                    return

                created = result.get("created") or []
                page_id = created[0]["id"] if created else None
                page_index = created[0]["page_index"] if created else total
                yield _ndjson(
                    {
                        "event": "page_uploaded",
                        "page_index": page_index,
                        "page_id": page_id,
                        "batch_page_count": result.get("batch_page_count"),
                    }
                )
                total += 1

            yield _ndjson({"event": "completed", "total": total})
        finally:
            try:
                scanner.close()
            except Exception:
                log.warning("close() del scanner falló (best-effort)", exc_info=True)
            try:
                saas.close()
            except Exception:
                log.warning(
                    "close() del saas client falló (best-effort)", exc_info=True
                )

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


class _ScanFailure:
    """Wrapper para que el bucle del stream pueda emitir un error y salir
    sin que la excepción se propague antes de yield la línea NDJSON.

    El generator-iterator de Python no permite un ``try/except`` que
    capture ``next()`` Y a la vez ceda control de vuelta al loop del
    caller, así que envolvemos la iteración con ``_safe_iter``.
    """

    __slots__ = ("exc",)

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc


def _safe_iter(it):
    """Itera sobre ``it`` capturando excepciones de ``next()`` para
    convertirlas en ``_ScanFailure`` que el caller emite como NDJSON."""
    iterator = iter(it)
    while True:
        try:
            yield next(iterator)
        except StopIteration:
            return
        except Exception as exc:
            yield _ScanFailure(exc)
            return
