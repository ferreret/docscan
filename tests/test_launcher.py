"""Tests del launcher UI."""

from __future__ import annotations

import pytest
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
            widget.item(i)
            for i in range(widget.count())
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
            widget.item(i)
            for i in range(widget.count())
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
        assert data["card"].tags  # icono, acento y etiquetas ya derivados

    def test_kebab_click_selects_and_requests_menu(
        self, qtbot, session_factory, seed_apps
    ):
        from app.db.repositories.application_repo import ApplicationRepository
        from PySide6.QtCore import Qt

        widget = AppListWidget()
        qtbot.addWidget(widget)
        widget.resize(700, 400)
        widget.show()
        with session_factory() as session:
            widget.populate(ApplicationRepository(session).get_all())
        item = widget.item(1)
        kebab = widget.kebab_rect_for(item)
        with qtbot.waitSignal(widget.menu_requested, timeout=1000):
            qtbot.mouseClick(
                widget.viewport(), Qt.MouseButton.LeftButton, pos=kebab.center()
            )
        assert widget.currentItem() is item

    def test_click_outside_kebab_does_not_open_menu(
        self, qtbot, session_factory, seed_apps
    ):
        from app.db.repositories.application_repo import ApplicationRepository
        from PySide6.QtCore import Qt

        widget = AppListWidget()
        qtbot.addWidget(widget)
        widget.resize(700, 400)
        widget.show()
        with session_factory() as session:
            widget.populate(ApplicationRepository(session).get_all())
        rect = widget.visualItemRect(widget.item(0))
        with qtbot.assertNotEmitted(widget.menu_requested):
            qtbot.mouseClick(
                widget.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
            )
        assert widget.currentRow() == 0

    def test_cards_grow_with_the_font_size(self, qtbot):
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QStyleOptionViewItem

        from app.ui.launcher.app_list_widget import AppCardDelegate

        delegate = AppCardDelegate()
        option = QStyleOptionViewItem()
        small, big = QFont(), QFont()
        small.setPixelSize(13)
        big.setPixelSize(17)
        option.font = small
        h_small = delegate.sizeHint(option, None).height()
        option.font = big
        assert delegate.sizeHint(option, None).height() > h_small


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
        self,
        qtbot,
        session_factory,
        seed_apps,
    ):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        # Sin selección, los botones del sidebar deben estar deshabilitados
        sb = window._sidebar
        assert not sb.get_button("open").isEnabled()
        assert not sb.get_button("configure").isEnabled()
        assert not sb.get_button("delete").isEnabled()

    def test_buttons_enabled_with_selection(
        self,
        qtbot,
        session_factory,
        seed_apps,
    ):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)
        sb = window._sidebar
        assert sb.get_button("open").isEnabled()
        assert sb.get_button("configure").isEnabled()
        assert sb.get_button("delete").isEnabled()

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

    def test_create_duplicate_app(self, qtbot, session_factory, seed_apps, monkeypatch):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        # El nombre duplicado dispara QMessageBox.warning, un modal que
        # bloquea el hilo esperando interacción. Se mockea para que el test
        # no cuelgue en entornos con display real.
        warned: list[str] = []
        monkeypatch.setattr(
            "app.ui.launcher.launcher_window.QMessageBox.warning",
            lambda *args, **kwargs: warned.append(args) or None,
        )
        # Intentar crear una app con nombre duplicado
        window._create_app("Facturas", "Duplicada")
        # No debe haber cambiado el conteo y se avisó al usuario
        assert window._app_list.count() == 3
        assert len(warned) == 1

    def test_open_signal(self, qtbot, session_factory, seed_apps):
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)

        with qtbot.waitSignal(window.app_opened, timeout=1000):
            window._on_open_app()

    def test_status_bar_counts_apps_and_says_ready(
        self, qtbot, session_factory, seed_apps
    ):
        """Como Flexibar: «N aplicación(es)» a la izquierda y «● Listo» a la derecha."""
        from PySide6.QtWidgets import QLabel

        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        assert window._lbl_app_count.text() == "3 aplicación(es)"
        textos = [lbl.text() for lbl in window.statusBar().findChildren(QLabel)]
        assert "Listo" in textos
        assert window.statusBar().findChild(QLabel, "statusDot") is not None

    def test_no_info_line_under_the_list(self, qtbot, session_factory, seed_apps):
        """La tarjeta ya muestra descripción, estado y fecha (Flexibar no la tiene)."""
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        assert not hasattr(window, "_info_label")

    def test_card_menu_has_the_sidebar_actions(
        self, qtbot, session_factory, seed_apps, monkeypatch
    ):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu

        monkeypatch.setattr(QMenu, "popup", lambda self, pos: None)
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)
        window._show_card_menu(QPoint(0, 0))
        textos = [a.text() for a in window._card_menu.actions() if not a.isSeparator()]
        assert textos == ["Abrir", "Configurar", "Clonar", "Exportar", "Eliminar"]
        assert all(
            not a.icon().isNull() for a in window._card_menu.actions() if a.text()
        )

    def test_card_menu_open_opens_the_app(
        self, qtbot, session_factory, seed_apps, monkeypatch
    ):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu

        monkeypatch.setattr(QMenu, "popup", lambda self, pos: None)
        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(0)
        window._show_card_menu(QPoint(0, 0))
        with qtbot.waitSignal(window.app_opened, timeout=1000):
            window._card_menu.actions()[0].trigger()

    def test_card_menu_needs_a_selection(self, qtbot, session_factory, seed_apps):
        from PySide6.QtCore import QPoint

        window = LauncherWindow(session_factory=session_factory)
        qtbot.addWidget(window)
        window._app_list.setCurrentRow(-1)
        window._show_card_menu(QPoint(0, 0))
        assert getattr(window, "_card_menu", None) is None
