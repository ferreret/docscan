"""Punto de entrada del agente local.

Ejecutar con::

    python -m docscan_local_agent

Por defecto bind a 127.0.0.1:47816. Variables de entorno con prefijo
``DOCSCAN_AGENT_`` permiten sobreescribir host/puerto.
"""

from __future__ import annotations

import logging

import uvicorn

from docscan_local_agent.main import create_app
from docscan_local_agent.settings import get_settings


def main() -> None:
    """Arranca uvicorn con la app del agente."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = get_settings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
