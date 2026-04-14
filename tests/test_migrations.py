"""Tests para la cadena de migraciones Alembic.

Verifica que las migraciones son la fuente de verdad del esquema:
`alembic upgrade head` sobre una BD vacía debe producir un esquema
equivalente al que genera `Base.metadata.create_all`.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.db.database import Base

# Importar todos los modelos para registrar las tablas en metadata
from app.models.application import Application  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.template import Template  # noqa: F401
from web.api.models import Invitation, Tenant, User  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _snapshot_schema(db_path: Path) -> dict:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    insp = inspect(engine)
    out: dict = {}
    for table in sorted(insp.get_table_names()):
        if table == "alembic_version":
            continue
        out[table] = {
            "cols": {
                c["name"]: (str(c["type"]), c["nullable"])
                for c in insp.get_columns(table)
            },
            "idxs": sorted(
                (tuple(i["column_names"]), i.get("unique", False))
                for i in insp.get_indexes(table)
            ),
            "uqs": sorted(
                tuple(u["column_names"]) for u in insp.get_unique_constraints(table)
            ),
            "fks": sorted(
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                    fk.get("options", {}).get("ondelete", ""),
                )
                for fk in insp.get_foreign_keys(table)
            ),
        }
    engine.dispose()
    return out


def test_alembic_upgrade_head_matches_create_all(tmp_path, monkeypatch):
    """La cadena completa de migraciones produce el mismo esquema que create_all.

    Sin este test, un hueco en el chain (ej. una tabla creada solo via
    `create_all` sin migración equivalente) pasaría desapercibido hasta
    intentar un despliegue limpio en producción.
    """
    from alembic import command
    from alembic.config import Config

    alembic_db = tmp_path / "alembic.db"
    create_all_db = tmp_path / "create_all.db"

    monkeypatch.setenv(
        "DOCSCAN_WEB_DATABASE__URL", f"sqlite:///{alembic_db.as_posix()}"
    )
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{create_all_db.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()

    assert _snapshot_schema(alembic_db) == _snapshot_schema(create_all_db)


def test_alembic_chain_is_linear():
    """No hay ramas sin resolver en el historial de migraciones."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    assert len(heads) == 1, f"Se esperaba un único head, hay {heads}"
