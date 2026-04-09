#!/usr/bin/env python3
"""Bootstrap de la BD para el contenedor web.

Lógica:
- Si la BD no tiene tabla `alembic_version` (primera vez), crea todo el
  esquema con ``Base.metadata.create_all`` y marca las migraciones como
  aplicadas con ``alembic stamp head``.
- Si ya existe, corre ``alembic upgrade head`` normalmente.

Así evitamos el problema de que las migraciones del proyecto asumen que
las tablas ya existen (el desktop las crea con ``create_all`` la primera
vez y Alembic solo maneja cambios evolutivos desde ese punto).
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, inspect

# Importar Base y todos los modelos para que metadata los registre
from app.db.database import Base
from app.models.application import Application  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.template import Template  # noqa: F401
from web.api.models import Tenant, User  # noqa: F401

from alembic import command
from alembic.config import Config


def main() -> None:
    database_url = os.environ.get("DOCSCAN_WEB_DATABASE__URL")
    if not database_url:
        sys.exit("ERROR: DOCSCAN_WEB_DATABASE__URL no definida")

    print(f"[bootstrap-db] Conectando a {database_url.split('@')[-1]}", flush=True)
    engine = create_engine(database_url)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    has_alembic = "alembic_version" in existing

    alembic_cfg = Config("/app/alembic.ini")
    alembic_cfg.set_main_option("script_location", "/app/alembic")

    if not has_alembic:
        print(
            "[bootstrap-db] BD vacía — create_all + stamp head",
            flush=True,
        )
        Base.metadata.create_all(engine)
        command.stamp(alembic_cfg, "head")
    else:
        print(
            f"[bootstrap-db] BD existente ({len(existing)} tablas) — upgrade head",
            flush=True,
        )
        command.upgrade(alembic_cfg, "head")

    engine.dispose()
    print("[bootstrap-db] Listo", flush=True)


if __name__ == "__main__":
    main()
