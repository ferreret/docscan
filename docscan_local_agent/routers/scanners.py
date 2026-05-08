"""Endpoint GET /scanners — lista los escáneres del PC vía scanner_service.

El agente delega 100% en ``app.services.scanner_service.create_scanner``
del desktop: el plan del sprint exige no duplicar lógica. Auto-selección
del backend disponible (sane en Linux, twain/wia en Windows).

Sólo accesible cuando el agente está emparejado. Razón: si no lo está,
no hay user/tenant a quien atribuir las páginas escaneadas, así que
ofrecer la lista de escáneres sería ruido.

**Cache de la lista**: ``sane.get_devices()`` carga todos los backends
activos en ``dll.conf`` y libsane-pixma (Canon BJNP de red) tiene un
bug que acumula fds altos y termina en ``FD_SETSIZE on fd_set``
(SIGABRT) tras 10-15 llamadas en una misma sesión. Cacheamos la lista
durante ``_CACHE_TTL_SECONDS`` y permitimos forzar refresco con
``?refresh=true`` (botón "Comprobar de nuevo" del frontend).
"""

from __future__ import annotations

import logging
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from docscan_local_agent.credentials import AgentCredentials
from docscan_local_agent.deps import (
    ScannerFactory,
    get_scanner_factory,
    require_paired,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["scanners"])

_CACHE_TTL_SECONDS = 60.0


class ScannerInfo(BaseModel):
    """Identificador de un escáner devuelto por list_sources()."""

    name: str
    backend: str  # "sane" | "twain" | "wia"


class ScannersResponse(BaseModel):
    """Respuesta de GET /scanners."""

    backend: str
    scanners: list[ScannerInfo]


_cache_lock = threading.Lock()
_cache: tuple[float, ScannersResponse] | None = None


def _invalidate_cache() -> None:
    """Limpia el cache. Útil para tests."""
    global _cache
    with _cache_lock:
        _cache = None


def _enumerate(factory: ScannerFactory) -> ScannersResponse:
    """Llama a list_sources() y construye la respuesta. Sin cache."""
    try:
        scanner = factory()
    except RuntimeError as exc:
        # create_scanner lanza RuntimeError cuando ningún backend está instalado.
        log.warning("Sin backends de escáner: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No hay backends de escáner disponibles: {exc}",
        ) from exc

    try:
        sources = scanner.list_sources()
    except Exception as exc:
        log.exception("Error enumerando escáneres")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enumerando escáneres: {exc}",
        ) from exc
    finally:
        # Liberar recursos USB siempre, incluso si list_sources() falló.
        # Si close() también falla, lo logueamos sin tapar el resultado.
        try:
            scanner.close()
        except Exception:
            log.warning("close() del scanner falló (best-effort)", exc_info=True)

    backend_name = scanner.backend_name
    return ScannersResponse(
        backend=backend_name,
        scanners=[ScannerInfo(name=src, backend=backend_name) for src in sources],
    )


@router.get("/scanners", response_model=ScannersResponse)
def list_scanners(
    refresh: bool = False,
    _creds: AgentCredentials = Depends(require_paired),
    factory: ScannerFactory = Depends(get_scanner_factory),
) -> ScannersResponse:
    """Lista los escáneres conectados al PC del agente.

    Args:
        refresh: si True, ignora el cache y vuelve a enumerar.

    Errores:
      - 401 si el agente no está emparejado (vía require_paired).
      - 503 si el sistema no tiene backends de escáner instalados.
      - 500 si el backend está pero falla al enumerar dispositivos.
    """
    global _cache
    now = time.monotonic()

    if not refresh:
        with _cache_lock:
            if _cache is not None and now - _cache[0] < _CACHE_TTL_SECONDS:
                return _cache[1]

    response = _enumerate(factory)
    with _cache_lock:
        _cache = (now, response)
    return response
