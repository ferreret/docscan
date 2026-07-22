"""Motor de base de datos SQLite con WAL mode obligatorio.

Provee el engine, la clase Base declarativa y la fábrica de sesiones.
WAL mode es necesario para concurrencia entre la UI y DocScanWorker.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event, create_engine, inspect, text, Engine
from sqlalchemy.orm import (
    DeclarativeBase,
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


def _project_root() -> Path:
    """Raíz desde la que resolver ``alembic.ini`` y el árbol ``alembic/``.

    - Binario congelado (PyInstaller): ``sys._MEIPASS``, donde el ``.spec`` deja
      ``alembic.ini`` en "." y el árbol en "alembic/".
    - Ejecución desde fuente: raíz del proyecto (este fichero está en
      ``app/db/database.py`` → ``parents[2]``).
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    """Config de Alembic resuelta de forma PyInstaller-safe.

    ``configure_logger=False`` evita que el ``fileConfig()`` de ``env.py`` pise
    el logging ya inicializado por la app.
    """
    root = _project_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg


def _column_default_sql(col, dialect) -> str | None:
    """Literal SQL para la cláusula DEFAULT de una columna, o ``None``.

    Prioriza ``server_default``; si no hay, usa el ``default`` escalar
    python-side (necesario en SQLite para columnas NOT NULL como
    ``notifications_json``, que en el modelo usa ``default="{}"``).
    """
    if col.server_default is not None:
        arg = col.server_default.arg
        try:
            return str(
                arg.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
            )
        except Exception:
            return getattr(arg, "text", str(arg))
    default = col.default
    if default is not None and getattr(default, "is_scalar", False):
        val = default.arg
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        return "'" + str(val).replace("'", "''") + "'"
    return None


def _reconcile_missing_columns(engine: Engine) -> None:
    """Añade por reflexión columnas del modelo ausentes en tablas reales.

    Solo itera tablas que existen en la BD. En SQLite, una columna NOT NULL solo
    se añade con NOT NULL si podemos aportar un DEFAULT; si no, se añade NULLable
    (con warning) para no romper el ALTER.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    dialect = engine.dialect
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                coltype = col.type.compile(dialect=dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'
                default_sql = _column_default_sql(col, dialect)
                if default_sql is not None:
                    ddl += f" DEFAULT {default_sql}"
                    if not col.nullable:
                        ddl += " NOT NULL"
                elif not col.nullable:
                    log.warning(
                        "Columna %s.%s es NOT NULL sin default; se añade NULLable",
                        table.name,
                        col.name,
                    )
                conn.execute(text(ddl))
                log.info("Reconciliada columna faltante: %s.%s", table.name, col.name)


def run_migrations(engine: Engine) -> None:
    """Lleva el esquema de la BD al día (alembic) al arrancar.

    Robusto a tres estados de BD:

    - **vacía**: ``upgrade head`` crea todo el esquema desde las migraciones.
    - **versionada** (tiene ``alembic_version``): ``upgrade head`` aplica lo que
      falte.
    - **legacy** (creada con ``create_all`` sin control alembic): reconcilia las
      columnas faltantes del modelo y hace ``stamp head`` para adoptarla; de ahí
      en adelante se gestiona con alembic.

    Reusa la conexión del ``engine`` (con sus pragmas WAL) vía
    ``cfg.attributes["connection"]``, que ``env.py`` reutiliza, de modo que las
    migraciones operan sobre esta BD y no sobre la de settings.
    """
    tables = set(inspect(engine).get_table_names())
    cfg = _alembic_config()
    if not tables or "alembic_version" in tables:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
    else:
        _reconcile_missing_columns(engine)
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.stamp(cfg, "head")
    log.info("Migraciones aplicadas (head)")


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Devuelve la fábrica de sesiones vinculada al engine."""
    return sessionmaker(bind=engine)
