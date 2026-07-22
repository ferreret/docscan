"""Alembic environment — conecta modelos ORM con las migraciones."""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importar Base y todos los modelos para que metadata los registre
from app.db.database import Base
from app.models.application import Application  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401

# Modelos exclusivos del web (require deps de web instaladas).
# Se importan opcionalmente para no romper el alembic del desktop si
# solo están las deps del desktop.
try:
    from web.api.models import Tenant, User  # noqa: F401
except ImportError:
    pass


config = context.config

if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

# Resolver URL de la BD:
# - Si DOCSCAN_WEB_DATABASE__URL está en el entorno, usarla (modo web/contenedor).
# - En caso contrario, caer al settings del desktop (modo local dev).
_web_url = os.environ.get("DOCSCAN_WEB_DATABASE__URL")
if _web_url:
    config.set_main_option("sqlalchemy.url", _web_url)
else:
    from config.settings import get_settings

    settings = get_settings()
    config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.database.path}")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migraciones en modo offline (genera SQL sin conexión)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migraciones en modo online (con conexión activa).

    Si el llamador ya pasó una conexión en ``config.attributes["connection"]``
    (caso del arranque desktop, que reusa el engine con WAL), la reutiliza para
    operar sobre esa misma BD. En caso contrario construye su propio engine
    desde ``sqlalchemy.url`` (CLI de alembic, docker-bootstrap-db, tests).
    """
    connection = config.attributes.get("connection", None)
    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
