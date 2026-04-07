"""Configuración de base de datos PostgreSQL para la API web.

Reutiliza los modelos ORM de app.models pero con motor PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from web.api.config import WebSettings, get_web_settings


def create_web_engine(settings: WebSettings | None = None):
    """Crea el engine SQLAlchemy para PostgreSQL."""
    if settings is None:
        settings = get_web_settings()

    engine = create_engine(
        settings.database.url,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
    )

    # WAL mode solo para SQLite (compatibilidad con tests)
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        dialect = engine.dialect.name
        if dialect == "sqlite":
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


_engine = None
_SessionFactory = None


def get_engine():
    """Obtiene o crea el engine singleton."""
    global _engine
    if _engine is None:
        _engine = create_web_engine()
    return _engine


def get_session_factory():
    """Obtiene o crea la session factory singleton."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """Dependency de FastAPI: proporciona una sesión por request."""
    factory = get_session_factory()
    with factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
