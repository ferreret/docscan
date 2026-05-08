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
from typing import Any

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
    supports_native_ui: bool = False
    """True si el driver tiene diálogo nativo (típico TWAIN/WIA en Windows).

    El frontend lo usa para elegir UX:
    - True → manda ``show_ui=True`` al endpoint /scan-* y el driver
      pinta su propio dialog en la sesión de escritorio del operario.
    - False → renderiza el ScannerOptionsDialog dinámico construido a
      partir de ``GET /scanners/{name}/options`` (caso típico SANE en
      Linux: SANE es API C, no tiene dialog propio).
    """


class ScannersResponse(BaseModel):
    """Respuesta de GET /scanners."""

    backend: str
    scanners: list[ScannerInfo]


class DeviceOptionInfo(BaseModel):
    """Opción individual del dispositivo serializada para el frontend.

    Réplica del ``DeviceOption`` de ``app/services/scanner_service.py``
    sin importar la dataclass del desktop (mantiene el agente
    desacoplado y empaquetable con PyInstaller).
    """

    name: str  # Identificador Python-safe (ej. "resolution")
    title: str  # Título legible
    description: str  # Descripción larga
    type: str  # "bool" | "int" | "fixed" | "string"
    unit: str  # "none" | "pixel" | "bit" | "mm" | "dpi" | "percent" | "microsecond"
    constraint: Any  # None | (min, max, step) | list[str|int]
    value: Any  # Valor actual
    is_active: bool = True
    is_settable: bool = True


class ScannerOptionsResponse(BaseModel):
    """Respuesta de GET /scanners/{name}/options."""

    scanner: str
    options: list[DeviceOptionInfo]


_cache_lock = threading.Lock()
_cache: tuple[float, ScannersResponse] | None = None

_options_cache_lock = threading.Lock()
_options_cache: dict[str, tuple[float, ScannerOptionsResponse]] = {}


def _invalidate_cache() -> None:
    """Limpia el cache de /scanners. Útil para tests."""
    global _cache
    with _cache_lock:
        _cache = None


def _invalidate_options_cache(scanner_name: str | None = None) -> None:
    """Limpia el cache de /scanners/{name}/options.

    Sin argumento limpia todo. Con scanner_name limpia esa entrada.
    """
    with _options_cache_lock:
        if scanner_name is None:
            _options_cache.clear()
        else:
            _options_cache.pop(scanner_name, None)


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
    supports_native_ui = bool(getattr(scanner, "supports_native_ui", False))
    return ScannersResponse(
        backend=backend_name,
        scanners=[
            ScannerInfo(
                name=src,
                backend=backend_name,
                supports_native_ui=supports_native_ui,
            )
            for src in sources
        ],
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


def _enumerate_options(
    factory: ScannerFactory, scanner_name: str
) -> ScannerOptionsResponse:
    """Construye la respuesta de /scanners/{name}/options. Sin cache.

    Valida que ``scanner_name`` aparece en ``list_sources()`` antes de
    consultar las opciones — así el 404 es limpio sin abrir el
    dispositivo USB del que el operario no tiene control.
    """
    try:
        scanner = factory()
    except RuntimeError as exc:
        log.warning("Sin backends de escáner: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No hay backends de escáner disponibles: {exc}",
        ) from exc

    try:
        sources = scanner.list_sources()
        if scanner_name not in sources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Escáner no existe: {scanner_name!r}",
            )

        try:
            raw_options = scanner.get_device_options(scanner_name)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("get_device_options falló para %s", scanner_name)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error consultando opciones: {exc}",
            ) from exc

        # ``raw_options`` puede ser ``list[DeviceOption]`` (dataclass del
        # desktop) o ``list[dict]`` (FakeScanner de tests). Pydantic v2
        # acepta ambos en ``model_validate`` siempre que los campos
        # coincidan.
        options = [
            DeviceOptionInfo.model_validate(o, from_attributes=True)
            for o in raw_options
        ]
        return ScannerOptionsResponse(scanner=scanner_name, options=options)
    finally:
        try:
            scanner.close()
        except Exception:
            log.warning("close() del scanner falló (best-effort)", exc_info=True)


@router.get(
    "/scanners/{scanner_name:path}/options",
    response_model=ScannerOptionsResponse,
)
def get_scanner_options(
    scanner_name: str,
    refresh: bool = False,
    _creds: AgentCredentials = Depends(require_paired),
    factory: ScannerFactory = Depends(get_scanner_factory),
) -> ScannerOptionsResponse:
    """Devuelve las opciones del dispositivo (modo, resolución, fuente, ...).

    Cachea por ``scanner_name`` con el mismo TTL que ``/scanners`` para
    evitar abrir el USB en cada request — query es caro y libsane-pixma
    sigue acumulando fds. ``?refresh=true`` invalida la entrada.

    Errores:
      - 401 sin pairing.
      - 404 si el scanner_name no aparece en list_sources().
      - 503 si no hay backends instalados.
      - 500 si get_device_options revienta.
    """
    now = time.monotonic()

    if not refresh:
        with _options_cache_lock:
            cached = _options_cache.get(scanner_name)
            if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
                return cached[1]

    response = _enumerate_options(factory, scanner_name)
    with _options_cache_lock:
        _options_cache[scanner_name] = (now, response)
    return response
