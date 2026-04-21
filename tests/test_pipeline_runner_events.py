"""Tests para el disparo del evento on_scan_complete en el runner web.

Enfoque: tests de integración ligeros. Se monta una BD SQLite en memoria
y se invoca ``run_pipeline_for_batch`` directamente (sin FastAPI). Se usa
``unittest.mock.patch`` sobre ``ScriptEngine.run_event`` para observar el
disparo sin depender de efectos secundarios del script.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base

# Importar modelos para registrar las tablas
from app.models.application import Application
from app.models.barcode import Barcode  # noqa: F401
from app.models.batch import Batch
from app.models.page import Page
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from web.api.models import Tenant, User  # noqa: F401

import web.api.database as _db_module
from web.api.storage import FilesystemStorage
from web.api.tasks.pipeline_runner import run_pipeline_for_batch


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def _test_engine():
    """Engine SQLite en memoria reutilizable entre hilos."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    # Inyectar el engine de test en los singletons de la web
    _db_module._engine = engine
    _db_module._SessionFactory = sessionmaker(bind=engine)
    yield engine
    _db_module._engine = None
    _db_module._SessionFactory = None
    engine.dispose()


@pytest.fixture
def session(_test_engine):
    factory = sessionmaker(bind=_test_engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "storage")


def _png_bytes(width: int = 4, height: int = 4) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _setup_batch(
    session,
    storage,
    *,
    events_json: str = "{}",
    pipeline_json: str = "[]",
) -> tuple[int, int]:
    """Crea application + batch + 1 page en BD + storage. Devuelve (app_id, batch_id)."""
    tenant = Tenant(name="t1", slug="t1")
    session.add(tenant)
    session.flush()

    app = Application(
        name="Test",
        pipeline_json=pipeline_json,
        events_json=events_json,
        tenant_id=tenant.id,
    )
    session.add(app)
    session.flush()

    batch = Batch(application_id=app.id, tenant_id=tenant.id, state="new")
    session.add(batch)
    session.flush()

    # Guardar imagen en storage y crear page
    key = storage.save(batch.id, 0, _png_bytes(), "png")
    page = Page(batch_id=batch.id, page_index=0, image_path=key)
    session.add(page)
    session.commit()

    return app.id, batch.id


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


class TestOnScanCompleteEvent:
    """Disparo del evento de ciclo de vida on_scan_complete."""

    def test_on_scan_complete_fires_after_pipeline(self, session, storage):
        events = {"on_scan_complete": ("def on_scan_complete(app, batch):\n    pass\n")}
        _, batch_id = _setup_batch(
            session,
            storage,
            events_json=json.dumps(events),
        )

        with patch(
            "web.api.tasks.pipeline_runner.ScriptEngine.run_event",
            return_value=None,
        ) as mock_run_event:
            run_pipeline_for_batch(batch_id, storage)

        # Debe invocarse exactamente una vez
        assert mock_run_event.call_count == 1
        args, kwargs = mock_run_event.call_args
        # Primer argumento posicional: script_id; segundo: entry_point
        assert args[0] == "on_scan_complete"
        assert args[1] == "on_scan_complete"
        # Debe recibir app y batch como kwargs
        assert "app" in kwargs
        assert "batch" in kwargs
        # batch_ctx debe reflejar el estado final del lote
        assert kwargs["batch"].id == batch_id

    def test_does_not_fire_if_empty_events_json(self, session, storage):
        _, batch_id = _setup_batch(session, storage, events_json="{}")

        with patch(
            "web.api.tasks.pipeline_runner.ScriptEngine.run_event",
            return_value=None,
        ) as mock_run_event:
            run_pipeline_for_batch(batch_id, storage)

        mock_run_event.assert_not_called()

    def test_does_not_fire_if_script_is_whitespace(self, session, storage):
        events = {"on_scan_complete": "   \n   "}
        _, batch_id = _setup_batch(
            session,
            storage,
            events_json=json.dumps(events),
        )

        with patch(
            "web.api.tasks.pipeline_runner.ScriptEngine.run_event",
            return_value=None,
        ) as mock_run_event:
            run_pipeline_for_batch(batch_id, storage)

        mock_run_event.assert_not_called()

    def test_does_not_fire_if_events_json_is_invalid(self, session, storage):
        _, batch_id = _setup_batch(session, storage, events_json="{not: valid json")

        with patch(
            "web.api.tasks.pipeline_runner.ScriptEngine.run_event",
            return_value=None,
        ) as mock_run_event:
            run_pipeline_for_batch(batch_id, storage)

        mock_run_event.assert_not_called()

        # El pipeline debe completarse normalmente (events inválido es tolerado)
        session.expire_all()
        batch = session.get(Batch, batch_id)
        assert batch.state == "read"

    def test_swallows_event_exceptions_and_batch_completes(self, session, storage):
        events = {
            "on_scan_complete": (
                "def on_scan_complete(app, batch):\n    raise RuntimeError('boom')\n"
            )
        }
        _, batch_id = _setup_batch(
            session,
            storage,
            events_json=json.dumps(events),
        )

        # No parcheamos run_event — dejamos que el script real lance la excepción.
        # El runner debe capturarla y terminar con batch.state='read'.
        run_pipeline_for_batch(batch_id, storage)

        session.expire_all()
        batch = session.get(Batch, batch_id)
        assert batch.state == "read"

    def test_compilation_error_does_not_break_pipeline(self, session, storage):
        # Sintaxis inválida → no debe compilar, pero el lote debe quedar 'read'
        events = {"on_scan_complete": "def broken(:\n    pass\n"}
        _, batch_id = _setup_batch(
            session,
            storage,
            events_json=json.dumps(events),
        )

        run_pipeline_for_batch(batch_id, storage)

        session.expire_all()
        batch = session.get(Batch, batch_id)
        assert batch.state == "read"

    def test_event_fires_after_batch_state_is_set(self, session, storage):
        """El batch_ctx pasado al evento debe reflejar el estado final."""
        events = {"on_scan_complete": ("def on_scan_complete(app, batch):\n    pass\n")}
        _, batch_id = _setup_batch(
            session,
            storage,
            events_json=json.dumps(events),
        )

        with patch(
            "web.api.tasks.pipeline_runner.ScriptEngine.run_event",
            return_value=None,
        ) as mock_run_event:
            run_pipeline_for_batch(batch_id, storage)

        assert mock_run_event.call_count == 1
        kwargs = mock_run_event.call_args.kwargs
        # El estado 'read' ya debe estar asignado cuando el evento se dispara
        assert kwargs["batch"].state == "read"
