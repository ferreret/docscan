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

# Importar modelos para que SQLAlchemy registre las relaciones
from app.models.application import Application  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from web.api.models import Tenant, User  # noqa: F401

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: inicialización y limpieza."""
    settings = get_web_settings()
    log.info(
        "DocScan Web API arrancando (mode=%s, debug=%s)",
        settings.deploy_mode,
        settings.debug,
    )

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("Conexión a base de datos OK")

    get_event_bus().attach_loop(asyncio.get_running_loop())

    yield

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
    from web.api.routers.applications import router as apps_router
    from web.api.routers.batches import router as batches_router
    from web.api.routers.pages import router as pages_router
    from web.api.routers.team import router as team_router
    from web.api.routers.ws import router as ws_router
    from web.api.routers.pipeline import router as pipeline_router
    from web.api.routers.events import router as events_router

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(apps_router, prefix="/api/applications", tags=["applications"])
    app.include_router(batches_router, prefix="/api/batches", tags=["batches"])
    app.include_router(pages_router, prefix="/api", tags=["pages"])
    app.include_router(team_router, prefix="/api", tags=["team"])
    app.include_router(pipeline_router, prefix="/api/applications", tags=["pipeline"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(events_router, prefix="/api/batches", tags=["events"])

    return app
