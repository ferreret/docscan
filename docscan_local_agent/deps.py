"""Dependencies de FastAPI compartidas por los routers del agente.

Centralizar los ``Depends`` aquí permite que los tests usen
``app.dependency_overrides`` para sustituir settings y factoría de
SaasClient por mocks (``tmp_path`` y ``MockTransport``).
"""

from __future__ import annotations

from typing import Callable

from docscan_local_agent.saas_client import SaasClient
from docscan_local_agent.settings import AgentSettings, get_settings as _build_settings

# Tipo de la factoría: dado un base_url devuelve un SaasClient listo.
SaasClientFactory = Callable[[str], SaasClient]


def get_settings() -> AgentSettings:
    """Devuelve los settings del agente (overridable en tests)."""
    return _build_settings()


def get_saas_client_factory() -> SaasClientFactory:
    """Devuelve una factoría que construye SaasClient real (overridable en tests)."""

    def _factory(base_url: str) -> SaasClient:
        return SaasClient(base_url)

    return _factory
