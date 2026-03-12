"""Tests del Gestor de Lotes (paso 20).

Cubre: modelo OperationHistory, repositorios, filtros de BatchRepository,
y widgets de la UI del batch manager.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.db.repositories.batch_repo import BatchRepository
from app.db.repositories.operation_history_repo import OperationHistoryRepository
from app.db.repositories.page_repo import PageRepository
from app.models.application import Application
from app.models.barcode import Barcode  # noqa: F401 — resolver relaciones
from app.models.batch import Batch, BATCH_STATES
from app.models.operation_history import OperationHistory
from app.models.page import Page
from app.models.template import Template  # noqa: F401 — resolver relaciones
from app.services.batch_service import BatchService


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture()
def engine():
    """Engine SQLite en memoria con WAL mode."""
    eng = create_engine("sqlite:///:memory:")

    def _set_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(eng, "connect", _set_pragmas)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Sesión de prueba."""
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def app_record(session) -> Application:
    """Aplicación de prueba."""
    app = Application(name="Test App", description="App de prueba")
    session.add(app)
    session.flush()
    return app


@pytest.fixture()
def sample_batches(session, app_record) -> list[Batch]:
    """Crea varios lotes en distintos estados."""
    batches = []
    for state in ("created", "read", "verified", "exported", "error_read"):
        b = Batch(
            application_id=app_record.id,
            state=state,
            hostname="workstation-1",
            username="tester",
            page_count=3,
        )
        session.add(b)
        batches.append(b)
    session.flush()
    return batches


# ------------------------------------------------------------------ #
# OperationHistory Model
# ------------------------------------------------------------------ #

class TestOperationHistory:
    """Tests del modelo OperationHistory."""

    def test_create_entry(self, session, sample_batches):
        batch = sample_batches[0]
        entry = OperationHistory(
            batch_id=batch.id,
            operation="state_change",
            old_state="created",
            new_state="read",
            username="tester",
            message="Cambio de estado",
        )
        session.add(entry)
        session.flush()

        assert entry.id is not None
        assert entry.batch_id == batch.id
        assert entry.operation == "state_change"
        assert entry.timestamp is not None

    def test_batch_relationship(self, session, sample_batches):
        batch = sample_batches[0]
        entry = OperationHistory(
            batch_id=batch.id,
            operation="test_op",
            username="tester",
        )
        session.add(entry)
        session.flush()

        # Relación inversa
        assert len(batch.history) >= 1
        assert batch.history[0].operation == "test_op"

    def test_repr(self, session, sample_batches):
        batch = sample_batches[0]
        entry = OperationHistory(
            batch_id=batch.id,
            operation="state_change",
        )
        session.add(entry)
        session.flush()
        assert "state_change" in repr(entry)


# ------------------------------------------------------------------ #
# OperationHistoryRepository
# ------------------------------------------------------------------ #

class TestOperationHistoryRepository:
    """Tests del repositorio de historial."""

    def test_add_and_get(self, session, sample_batches):
        repo = OperationHistoryRepository(session)
        batch = sample_batches[0]

        entry = OperationHistory(
            batch_id=batch.id,
            operation="state_change",
            old_state="created",
            new_state="read",
            username="tester",
        )
        result = repo.add(entry)
        assert result.id is not None

        history = repo.get_by_batch(batch.id)
        assert len(history) == 1
        assert history[0].operation == "state_change"

    def test_multiple_entries_ordered(self, session, sample_batches):
        repo = OperationHistoryRepository(session)
        batch = sample_batches[0]

        for i, op in enumerate(["create", "state_change", "transfer"]):
            entry = OperationHistory(
                batch_id=batch.id,
                operation=op,
                username="tester",
            )
            repo.add(entry)

        history = repo.get_by_batch(batch.id)
        assert len(history) == 3

    def test_empty_history(self, session, sample_batches):
        repo = OperationHistoryRepository(session)
        history = repo.get_by_batch(999)
        assert history == []


# ------------------------------------------------------------------ #
# BatchRepository — Filtros
# ------------------------------------------------------------------ #

class TestBatchRepositoryFilters:
    """Tests de los métodos de filtro del BatchRepository."""

    def test_get_all(self, session, sample_batches):
        repo = BatchRepository(session)
        all_batches = repo.get_all()
        assert len(all_batches) == 5

    def test_filter_by_state(self, session, sample_batches):
        repo = BatchRepository(session)
        result = repo.get_filtered(state="created")
        assert len(result) == 1
        assert result[0].state == "created"

    def test_filter_by_app(self, session, sample_batches, app_record):
        repo = BatchRepository(session)
        result = repo.get_filtered(application_id=app_record.id)
        assert len(result) == 5

        result = repo.get_filtered(application_id=999)
        assert len(result) == 0

    def test_filter_by_hostname(self, session, sample_batches):
        repo = BatchRepository(session)
        result = repo.get_filtered(hostname="workstation-1")
        assert len(result) == 5

        result = repo.get_filtered(hostname="unknown")
        assert len(result) == 0

    def test_filter_combined(self, session, sample_batches, app_record):
        repo = BatchRepository(session)
        result = repo.get_filtered(
            state="exported",
            application_id=app_record.id,
            hostname="workstation-1",
        )
        assert len(result) == 1
        assert result[0].state == "exported"

    def test_get_distinct_hostnames(self, session, sample_batches):
        repo = BatchRepository(session)
        hostnames = repo.get_distinct_hostnames()
        assert "workstation-1" in hostnames

    def test_filter_by_date(self, session, sample_batches):
        repo = BatchRepository(session)
        now = datetime.now()
        result = repo.get_filtered(
            date_from=datetime(2020, 1, 1),
            date_to=datetime(now.year + 1, 1, 1),
        )
        assert len(result) == 5


# ------------------------------------------------------------------ #
# UI Widgets (pytest-qt)
# ------------------------------------------------------------------ #

class TestBatchListWidget:
    """Tests del widget de lista de lotes."""

    def test_set_batches(self, qtbot):
        from app.ui.batch_manager.batch_list_widget import BatchListWidget

        widget = BatchListWidget()
        qtbot.addWidget(widget)

        batches = [
            {
                "id": 1,
                "app_name": "Test App",
                "state": "created",
                "page_count": 5,
                "hostname": "pc-01",
                "created_at": datetime(2026, 1, 15, 10, 30),
                "updated_at": datetime(2026, 1, 15, 10, 35),
            },
            {
                "id": 2,
                "app_name": "Test App",
                "state": "exported",
                "page_count": 10,
                "hostname": "pc-02",
                "created_at": datetime(2026, 1, 16, 9, 0),
                "updated_at": datetime(2026, 1, 16, 9, 5),
            },
        ]

        widget.set_batches(batches)
        assert widget.rowCount() == 2

    def test_get_selected_none(self, qtbot):
        from app.ui.batch_manager.batch_list_widget import BatchListWidget

        widget = BatchListWidget()
        qtbot.addWidget(widget)
        assert widget.get_selected_batch_id() is None

    def test_signal_batch_selected(self, qtbot):
        from app.ui.batch_manager.batch_list_widget import BatchListWidget

        widget = BatchListWidget()
        qtbot.addWidget(widget)

        widget.set_batches([{
            "id": 42,
            "app_name": "Test",
            "state": "read",
            "page_count": 1,
            "hostname": "pc",
            "created_at": None,
            "updated_at": None,
        }])

        with qtbot.waitSignal(widget.batch_selected, timeout=1000):
            widget.selectRow(0)

    def test_state_colors(self, qtbot):
        from app.ui.batch_manager.batch_list_widget import BatchListWidget

        widget = BatchListWidget()
        qtbot.addWidget(widget)

        widget.set_batches([{
            "id": 1,
            "app_name": "App",
            "state": "error_read",
            "page_count": 0,
            "hostname": "",
            "created_at": None,
            "updated_at": None,
        }])

        # El item debe tener un fondo con color (tinte de estado)
        item = widget.item(0, 0)
        bg = item.background().color()
        assert bg.alpha() > 0  # Tiene color de fondo con alpha


class TestBatchDetailPanel:
    """Tests del panel de detalle."""

    def test_set_general_info(self, qtbot):
        from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel

        panel = BatchDetailPanel()
        qtbot.addWidget(panel)

        panel.set_general_info({
            "id": 1,
            "app_name": "Mi App",
            "state": "read",
            "hostname": "pc-01",
            "username": "admin",
            "page_count": 10,
            "created_at": datetime(2026, 3, 1, 12, 0),
            "updated_at": datetime(2026, 3, 1, 12, 5),
            "folder_path": "/tmp/batch_1",
        })

        assert panel._lbl_id.text() == "1"
        assert panel._lbl_app.text() == "Mi App"
        assert panel._lbl_state.text() == "Leído"

    def test_set_stats(self, qtbot):
        from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel

        panel = BatchDetailPanel()
        qtbot.addWidget(panel)

        panel.set_stats({
            "total_pages": 20,
            "needs_review": 3,
            "excluded": 1,
            "blank": 2,
            "with_errors": 4,
        })

        assert panel._lbl_stat_total.text() == "20"
        assert panel._lbl_stat_review.text() == "3"

    def test_set_pages(self, qtbot):
        from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel

        panel = BatchDetailPanel()
        qtbot.addWidget(panel)

        panel.set_pages([
            {"page_index": 0, "needs_review": True, "is_excluded": False,
             "is_blank": False, "ocr_text": "hello", "error_count": 0},
            {"page_index": 1, "needs_review": False, "is_excluded": True,
             "is_blank": False, "ocr_text": "", "error_count": 2},
        ])

        assert panel._pages_table.rowCount() == 2

    def test_set_history(self, qtbot):
        from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel

        panel = BatchDetailPanel()
        qtbot.addWidget(panel)

        panel.set_history([
            {
                "timestamp": datetime(2026, 3, 1, 10, 0),
                "operation": "state_change",
                "old_state": "created",
                "new_state": "read",
                "username": "tester",
                "message": "Cambio",
            },
        ])

        assert panel._history_table.rowCount() == 1

    def test_clear_all(self, qtbot):
        from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel

        panel = BatchDetailPanel()
        qtbot.addWidget(panel)

        panel.set_general_info({
            "id": 1, "app_name": "Test", "state": "read",
            "hostname": "", "username": "", "page_count": 5,
            "created_at": None, "updated_at": None, "folder_path": "",
        })
        panel.clear_all()

        assert panel._lbl_id.text() == "-"
        assert panel._lbl_stat_total.text() == "0"


class TestBatchManagerWindow:
    """Tests básicos de la ventana principal del gestor."""

    def test_window_creation(self, qtbot, engine):
        from app.ui.batch_manager.batch_manager_window import BatchManagerWindow

        factory = sessionmaker(bind=engine)

        # Crear tablas y una app de prueba
        with factory() as s:
            app = Application(name="Test", description="")
            s.add(app)
            s.commit()

        window = BatchManagerWindow(session_factory=factory)
        qtbot.addWidget(window)

        assert window.windowTitle() == "DocScan Studio — Histórico de Lotes"
        assert window._lbl_count.text() == "0 lote(s)"

    def test_refresh_with_batches(self, qtbot, engine):
        from app.ui.batch_manager.batch_manager_window import BatchManagerWindow

        factory = sessionmaker(bind=engine)

        with factory() as s:
            app = Application(name="Test App", description="")
            s.add(app)
            s.flush()
            now = datetime.now()
            for state in ("created", "read", "exported"):
                b = Batch(
                    application_id=app.id,
                    state=state,
                    hostname="pc-01",
                    username="tester",
                    page_count=5,
                    created_at=now,
                    updated_at=now,
                )
                s.add(b)
            s.commit()

        window = BatchManagerWindow(session_factory=factory)
        qtbot.addWidget(window)

        assert window._lbl_count.text() == "3 lote(s)"

    def test_timer_running(self, qtbot, engine):
        from app.ui.batch_manager.batch_manager_window import (
            BatchManagerWindow,
            DEFAULT_REFRESH_INTERVAL,
        )

        factory = sessionmaker(bind=engine)
        with factory() as s:
            s.add(Application(name="App", description=""))
            s.commit()

        window = BatchManagerWindow(session_factory=factory)
        qtbot.addWidget(window)

        assert window._refresh_timer.isActive()
        assert window._refresh_timer.interval() == DEFAULT_REFRESH_INTERVAL
