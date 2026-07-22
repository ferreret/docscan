"""Tests para la cadena de migraciones Alembic.

Verifica que las migraciones son la fuente de verdad del esquema:
`alembic upgrade head` sobre una BD vacía debe producir un esquema
equivalente al que genera `Base.metadata.create_all`.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect

from app.db.database import (
    Base,
    create_db_engine,
    run_migrations,
    _alembic_config,
)

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


# ----------------------------------------------------------------------
# run_migrations() al arranque del desktop (robusto a 3 estados de BD)
# ----------------------------------------------------------------------

# Tablas del proceso desktop (create_all del desktop real NO incluye las web).
_DESKTOP_TABLES = [
    Application.__table__,
    Batch.__table__,
    Page.__table__,
    Barcode.__table__,
    Template.__table__,
    OperationHistory.__table__,
]


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _stamped_version(db_path: Path) -> str | None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    insp = inspect(engine)
    if "alembic_version" not in insp.get_table_names():
        engine.dispose()
        return None
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    engine.dispose()
    return row[0] if row else None


def _applications_columns(db_path: Path) -> set[str]:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    cols = {c["name"] for c in inspect(engine).get_columns("applications")}
    engine.dispose()
    return cols


def test_run_migrations_empty_db_matches_create_all_and_stamps_head(tmp_path):
    """BD nueva: run_migrations crea el esquema (== create_all) y sella el head."""
    db = tmp_path / "empty.db"
    engine = create_db_engine(db_path=db)
    run_migrations(engine)
    engine.dispose()

    create_all_db = tmp_path / "create_all.db"
    e2 = create_engine(f"sqlite:///{create_all_db.as_posix()}")
    Base.metadata.create_all(e2)
    e2.dispose()

    assert _snapshot_schema(db) == _snapshot_schema(create_all_db)
    assert _stamped_version(db) == _alembic_head()


def test_run_migrations_legacy_reconciles_missing_column_and_stamps(tmp_path):
    """BD legacy (create_all desktop sin versión, falta una columna del modelo):
    run_migrations la reconcilia por reflexión y sella el head.
    """
    db = tmp_path / "legacy.db"
    e = create_engine(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(e, tables=_DESKTOP_TABLES)
    with e.begin() as c:
        c.exec_driver_sql(
            "ALTER TABLE applications DROP COLUMN notifications_json"
        )
    e.dispose()
    assert "notifications_json" not in _applications_columns(db)
    assert _stamped_version(db) is None

    engine = create_db_engine(db_path=db)
    run_migrations(engine)
    engine.dispose()

    assert "notifications_json" in _applications_columns(db)
    assert _stamped_version(db) == _alembic_head()


def test_run_migrations_userlike_versioned_reaches_head(tmp_path):
    """BD tipo la del usuario: create_all desktop sin notifications_json,
    stampeada en bf8a2c4d1e9a. run_migrations debe llegar al head sin que
    e5b7 (drop_constraint) reviente, y añadir notifications_json.
    """
    db = tmp_path / "userlike.db"
    e = create_engine(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(e, tables=_DESKTOP_TABLES)
    with e.begin() as c:
        c.exec_driver_sql(
            "ALTER TABLE applications DROP COLUMN notifications_json"
        )
    with e.connect() as conn:
        cfg = _alembic_config()
        cfg.attributes["connection"] = conn
        command.stamp(cfg, "bf8a2c4d1e9a")
    e.dispose()

    engine = create_db_engine(db_path=db)
    run_migrations(engine)  # e5b7 no debe petar
    engine.dispose()

    assert "notifications_json" in _applications_columns(db)
    assert _stamped_version(db) == _alembic_head()


def test_e5b7_idempotent_when_named_constraint_absent(tmp_path):
    """e5b7 sobre applications de create_all (sin el constraint nombrado
    'applications_name_key') no lanza y deja uq_applications_tenant_name.
    """
    db = tmp_path / "e5b7.db"
    e = create_engine(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(e, tables=_DESKTOP_TABLES)
    with e.connect() as conn:
        cfg = _alembic_config()
        cfg.attributes["connection"] = conn
        command.stamp(cfg, "bf8a2c4d1e9a")
        command.upgrade(cfg, "e5b7c3d94f10")  # no debe lanzar
    e.dispose()

    engine = create_engine(f"sqlite:///{db.as_posix()}")
    uqs = {
        u["name"] for u in inspect(engine).get_unique_constraints("applications")
    }
    engine.dispose()
    assert "uq_applications_tenant_name" in uqs
