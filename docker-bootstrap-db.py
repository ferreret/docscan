#!/usr/bin/env python3
"""Bootstrap de la BD para el contenedor web.

Ejecuta ``alembic upgrade head``. Las migraciones son la fuente de verdad
del esquema: una BD vacía se construye desde cero al aplicar la cadena
completa, y una BD ya existente se lleva al head aplicando solo lo que
falte.
"""

from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config


def main() -> None:
    database_url = os.environ.get("DOCSCAN_WEB_DATABASE__URL")
    if not database_url:
        sys.exit("ERROR: DOCSCAN_WEB_DATABASE__URL no definida")

    print(f"[bootstrap-db] Conectando a {database_url.split('@')[-1]}", flush=True)

    alembic_cfg = Config("/app/alembic.ini")
    alembic_cfg.set_main_option("script_location", "/app/alembic")

    print("[bootstrap-db] alembic upgrade head", flush=True)
    command.upgrade(alembic_cfg, "head")

    print("[bootstrap-db] Listo", flush=True)


if __name__ == "__main__":
    main()
