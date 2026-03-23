"""Alembic environment — conecta modelos ORM con las migraciones."""

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

from config.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Configurar URL de la BD dinámicamente desde settings
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
    """Migraciones en modo online (con conexión activa)."""
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
