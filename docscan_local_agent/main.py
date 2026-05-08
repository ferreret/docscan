"""Factoría FastAPI del agente local."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docscan_local_agent import __version__
from docscan_local_agent.routers import pair as pair_router
from docscan_local_agent.routers import scan as scan_router
from docscan_local_agent.routers import scan_adf as scan_adf_router
from docscan_local_agent.routers import scan_upload as scan_upload_router
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

    # CORS amplio: el agente sólo escucha en 127.0.0.1, así que cualquier
    # web que llegue aquí corre en el mismo equipo del operario. La auth
    # interna del agente es por presencia de ``agent.json`` en disco, no
    # por cookies, así que ``allow_credentials=False`` cierra el riesgo de
    # ataques CSRF desde una web maliciosa que el operario haya abierto.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(status_router.router)
    app.include_router(pair_router.router)
    app.include_router(scanners_router.router)
    app.include_router(scan_router.router)
    app.include_router(scan_upload_router.router)
    app.include_router(scan_adf_router.router)

    return app
