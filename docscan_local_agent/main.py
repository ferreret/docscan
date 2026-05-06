"""Factoría FastAPI del agente local."""

from __future__ import annotations

from fastapi import FastAPI

from docscan_local_agent import __version__
from docscan_local_agent.routers import pair as pair_router
from docscan_local_agent.routers import scan as scan_router
from docscan_local_agent.routers import scanners as scanners_router
from docscan_local_agent.routers import status as status_router


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI del agente.

    Devuelve una instancia limpia (sin estado compartido) — los tests
    crean una app por test y los entry points productivos crean una en
    ``__main__.py``.
    """
    app = FastAPI(
        title="DocScan Local Agent",
        version=__version__,
        description=(
            "Proceso local que expone el escáner del PC a la web SaaS de "
            "DocScan Studio. No accesible desde fuera del equipo."
        ),
    )

    app.include_router(status_router.router)
    app.include_router(pair_router.router)
    app.include_router(scanners_router.router)
    app.include_router(scan_router.router)

    return app
