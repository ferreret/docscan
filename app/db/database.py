"""Motor de base de datos SQLite con WAL mode obligatorio.

Provee el engine, la clase Base declarativa y la fábrica de sesiones.
WAL mode es necesario para concurrencia entre la UI y DocScanWorker.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import event, create_engine, Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    Session,
    sessionmaker,
)

from config.settings import get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM."""

    pass


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Configura WAL mode y pragmas de rendimiento en cada conexión."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(db_path: Path | None = None) -> Engine:
    """Crea el engine SQLAlchemy con WAL mode.

    Args:
        db_path: Ruta a la BD. Si es None, usa la de settings.
    """
    settings = get_settings()
    path = db_path or settings.database.path
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        echo=settings.database.echo,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)

    log.info("Engine SQLite creado: %s (WAL mode)", path)
    return engine


def create_tables(engine: Engine) -> None:
    """Crea todas las tablas definidas en los modelos."""
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Devuelve la fábrica de sesiones vinculada al engine."""
    return sessionmaker(bind=engine)
