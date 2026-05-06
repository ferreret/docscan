"""FastAPI app factory para DocScan Studio Web."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from web.api.config import get_web_settings
from web.api.database import get_engine, reset_engine
from web.api.events import get_event_bus
from web.api.tasks.queue import close_arq_pool, enqueue_or_run, get_arq_pool

# Side-effect imports: registran modelos SQLAlchemy y runners inline.
from web.api import _register_models  # noqa: F401
from web.api.tasks import pipeline_runner  # noqa: F401
from web.api.tasks import transfer_runner  # noqa: F401

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: inicialización y limpieza."""
    settings = get_web_settings()
    log.info(
        "DocScan Web API arrancando (mode=%s, debug=%s, tasks_inline=%s)",
        settings.deploy_mode,
        settings.debug,
        settings.tasks.inline,
    )

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("Conexión a base de datos OK")

    get_event_bus().attach_loop(asyncio.get_running_loop())

    # Abrir pool ARQ y disparar recovery solo si NO estamos en modo inline.
    # En tests no hay Redis y el recovery se invoca manualmente.
    if not settings.tasks.inline:
        await get_arq_pool()  # Inicializa el singleton.
        try:
            await enqueue_or_run("recovery_job")
            log.info("recovery_job enrolado al arrancar")
        except Exception as e:
            # No bloquear el arranque del API si Redis está caído.
            log.warning("No se pudo enrolar recovery_job: %s", e)

    yield

    if not settings.tasks.inline:
        await close_arq_pool()
    reset_engine()
    log.info("DocScan Web API detenida")


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI."""
    settings = get_web_settings()

    app = FastAPI(
        title="DocScan Studio API",
        description="API REST para DocScan Studio Web",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    from web.api.routers.health import router as health_router
    from web.api.auth.router import router as auth_router
    from web.api.routers.admin_tenants import router as admin_tenants_router
    from web.api.routers.admin_users import router as admin_users_router
    from web.api.routers.applications import router as apps_router
    from web.api.routers.batches import router as batches_router
    from web.api.routers.pages import router as pages_router
    from web.api.routers.team import router as team_router
    from web.api.routers.ws import router as ws_router
    from web.api.routers.pipeline import router as pipeline_router
    from web.api.routers.events import router as events_router
    from web.api.routers.agent import router as agent_router

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(
        admin_tenants_router, prefix="/api/admin/tenants", tags=["admin"]
    )
    app.include_router(admin_users_router, prefix="/api/admin/users", tags=["admin"])
    app.include_router(apps_router, prefix="/api/applications", tags=["applications"])
    app.include_router(batches_router, prefix="/api/batches", tags=["batches"])
    app.include_router(pages_router, prefix="/api", tags=["pages"])
    app.include_router(team_router, prefix="/api", tags=["team"])
    app.include_router(pipeline_router, prefix="/api/applications", tags=["pipeline"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(events_router, prefix="/api/batches", tags=["events"])
    app.include_router(agent_router, prefix="/api/agent", tags=["agent"])

    return app
