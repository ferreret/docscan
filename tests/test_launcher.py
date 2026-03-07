"""Tests del launcher UI."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.ui.launcher.launcher_window import LauncherWindow
from app.ui.launcher.app_list_widget import AppListWidget
from app.ui.launcher.new_app_dialog import NewAppDialog


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def seed_apps(session_factory):
    """Crea aplicaciones de prueba en la BD."""
    with session_factory() as session:
        for name in ["Facturas", "Albaranes", "Contratos"]:
            session.add(Application(name=name, description=f"App de {name}"))
        session.commit()


# ------------------------------------------------------------------
# AppListWidget
# ------------------------------------------------------------------


class TestAppListWidget:
    def test_populate(self, qtbot, session_factory, seed_apps):
        from app.db.repositories.application_repo import ApplicationRepository

        widget = AppListWidget()
        qtbot.addWidget(widget)

        with session_factory() as session:
            repo = ApplicationRepository(session)
            apps = repo.get_all()
            widget.populate(apps)

        assert widget.count() == 3

    def test_filter(self, qtbot, session_factory, seed_apps):
        from app.db.repositories.application_repo import ApplicationRepository

        widget = AppListWidget()
        qtbot.addWidget(widget)

        with session_factory() as session:
            repo = ApplicationRepository(session)
            widget.populate(repo.get_all())

        widget.filter_apps("fact")
        visible = [
            widget.item(i) for i in range(widget.count())
            if not widget.item(i).isHidden()
        ]
        assert len(visible) == 1
        assert visible[0].text() == "Facturas"

    def test_filter_clear(self, qtbot, session_factory, seed_apps):
        from app.db.repositories.application_repo import ApplicationRepository

        widget = AppListWidget()
        qtbot.addWidget(widget)

        with session_factory() as session:
            repo = ApplicationRepository(session)
            widget.populate(repo.get_all())

        widget.filter_apps("fact")
        widget.filter_apps("")
        visible = [
            widget.item(i) for i in range(widget.count())
            if not widget.item(i).isHidden()
        ]
        assert len(visible) == 3

    def test_selected_app_id_none(self, qtbot):
        widget = AppListWidget()
        qtbot.addWidget(widget)
        assert widget.selected_app_id() is None

    def test_selected_app_data(self, qtbot, session_factory, seed_apps):
        from app.db.repositories.application_repo import ApplicationRepository

        widget = AppListWidget()
        qtbot.addWidget(widget)

        with session_factory() as session:
            repo = ApplicationRepository(session)
            widget.populate(repo.get_all())

        widget.setCurrentRow(0)
        data = widget.selected_app_data()
        assert data is not None
        assert "name" in data


# ------------------------------------------------------------------
# NewAppDialog
# ------------------------------------------------------------------


class TestNewAppDialog:
    def test_empty_name_no_accept(self, qtbot):
        dialog = NewAppDialog()
        qtbot.addWidget(dialog)
        dialog._name_edit.setText("")
        dialog._validate_and_accept()
        # No debería haber aceptado (el diálogo sigue abierto)
        assert dialog.app_name() == ""

    def test_valid_name(self, qtbot):
        dialog = NewAppDialog()
        qtbot.addWidget(dialog)
        dialog._name_edit.setText("Mi App")
        dialog._desc_edit.setPlainText("Descripción test")
        assert dialog.app_name() == "Mi App"
        assert dialog.app_description() == "Descripción test"


# ------------------------------------------------------------------
# LauncherWindow
# ------------------------------------------------------------------


class TestLauncherWindow:
    def test_window_creates(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        assert window.windowTitle() == "DocScan Studio"
        assert window._app_list.count() == 3

    def test_buttons_disabled_without_selection(
        self, qtbot, session_factory, seed_apps,
    ):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        # Sin selección, los botones deben estar deshabilitados
        assert not window._btn_open.isEnabled()
        assert not window._btn_configure.isEnabled()
        assert not window._btn_delete.isEnabled()

    def test_buttons_enabled_with_selection(
        self, qtbot, session_factory, seed_apps,
    ):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)
        assert window._btn_open.isEnabled()
        assert window._btn_configure.isEnabled()
        assert window._btn_delete.isEnabled()

    def test_filter_integration(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._filter_edit.setText("alb")
        visible = [
            window._app_list.item(i)
            for i in range(window._app_list.count())
            if not window._app_list.item(i).isHidden()
        ]
        assert len(visible) == 1

    def test_create_app(self, qtbot, session_factory):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        assert window._app_list.count() == 0

        window._create_app("Nueva App", "Descripción")
        assert window._app_list.count() == 1

    def test_create_duplicate_app(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        # Intentar crear una app con nombre duplicado
        window._create_app("Facturas", "Duplicada")
        # No debe haber cambiado el conteo
        assert window._app_list.count() == 3

    def test_open_signal(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)

        with qtbot.waitSignal(window.app_opened, timeout=1000):
            window._on_open_app()

    def test_info_label_updates(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)
        assert "Facturas" in window._info_label.text() or \
               "Albaranes" in window._info_label.text()
