"""Dependencies de FastAPI compartidas por los routers del agente.

Centralizar los ``Depends`` aquí permite que los tests usen
``app.dependency_overrides`` para sustituir settings y factoría de
SaasClient por mocks (``tmp_path`` y ``MockTransport``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from fastapi import Depends, HTTPException, status

from docscan_local_agent.credentials import AgentCredentials, load_credentials
from docscan_local_agent.saas_client import SaasClient
from docscan_local_agent.settings import AgentSettings, get_settings as _build_settings

if TYPE_CHECKING:
    from app.services.scanner_service import BaseScanner

# Tipo de la factoría: dado un base_url devuelve un SaasClient listo.
SaasClientFactory = Callable[[str], SaasClient]

# Tipo de la factoría de scanner: sin args devuelve un BaseScanner listo.
ScannerFactory = Callable[[], "BaseScanner"]


def get_settings() -> AgentSettings:
    """Devuelve los settings del agente (overridable en tests)."""
    return _build_settings()


def get_saas_client_factory() -> SaasClientFactory:
    """Devuelve una factoría que construye SaasClient real (overridable en tests)."""

    def _factory(base_url: str) -> SaasClient:
        return SaasClient(base_url)

    return _factory


def require_paired(
    settings: AgentSettings = Depends(get_settings),
) -> AgentCredentials:
    """Dependency para endpoints que exigen un agente ya emparejado.

    Lee ``agent.json`` del ``config_dir``. Si no existe (o está corrupto),
    devuelve 401 con un detalle accionable. Si está, devuelve las
    credenciales para que el handler las use (p. ej. para llamar al SaaS).
    """
    creds = load_credentials(settings.config_dir)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agente no emparejado. Empareja primero con POST /pair.",
        )
    return creds


def get_scanner_factory() -> ScannerFactory:
    """Devuelve una factoría que construye un BaseScanner real.

    Por defecto delega en ``app.services.scanner_service.create_scanner``
    (auto-selección del backend disponible). Los tests overridean para
    inyectar un ``FakeScanner`` sin tocar SANE/TWAIN.

    El import del scanner_service se hace lazy para que el agente arranque
    sin SANE instalado (``GET /status`` y ``POST /pair`` no necesitan
    escaner).
    """
    from app.services.scanner_service import create_scanner

    return create_scanner
