"""Ventana principal del Launcher.

Lista las aplicaciones disponibles y permite abrir, crear,
configurar o eliminar aplicaciones.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.launcher.app_list_widget import AppListWidget
from app.ui.theme_manager import ThemeManager

log = logging.getLogger(__name__)


class LauncherWindow(QMainWindow):
    """Ventana principal del launcher de DocScan Studio.

    Signals:
        app_opened: Emitida cuando el usuario abre una aplicación (app_id).
        app_configure: Emitida cuando se quiere configurar una app (app_id).
        batch_manager_requested: Emitida para abrir el gestor de lotes.
    """

    app_opened = Signal(int)
    app_configure = Signal(int)
    batch_manager_requested = Signal()

    def __init__(self, session_factory: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._theme_manager = ThemeManager()
        self._setup_ui()
        self._connect_signals()
        self._load_apps()

    def _setup_ui(self) -> None:
        self.setWindowTitle("DocScan Studio")
        self.setMinimumSize(800, 560)

        # --- Toolbar ---
        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._btn_new = QPushButton("Nueva")
        self._btn_new.setProperty("cssClass", "primary")
        self._btn_open = QPushButton("Abrir")
        self._btn_configure = QPushButton("Configurar")
        self._btn_delete = QPushButton("Eliminar")
        self._btn_delete.setProperty("cssClass", "danger")
        self._btn_refresh = QPushButton("Actualizar")
        self._btn_batch_manager = QPushButton("Gestor de Lotes")

        toolbar.addWidget(self._btn_new)
        toolbar.addWidget(self._btn_open)
        toolbar.addWidget(self._btn_configure)
        toolbar.addWidget(self._btn_delete)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_refresh)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_batch_manager)

        # Spacer para empujar el toggle de tema a la derecha
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        from app.ui.icon_factory import (
            icon_font_decrease,
            icon_font_increase,
        )

        self._btn_theme = QPushButton()
        self._btn_theme.setToolTip("Cambiar tema claro/oscuro")
        self._update_theme_button()
        toolbar.addWidget(self._btn_theme)

        icon_size = 20
        icon_color = "#cdd6f4" if self._theme_manager.is_dark else "#4c4f69"

        self._btn_font_up = QPushButton()
        self._btn_font_up.setIcon(icon_font_increase(icon_color, 32))
        self._btn_font_up.setToolTip("Aumentar tamaño de fuente")
        self._btn_font_up.setFixedSize(34, 34)
        self._btn_font_down = QPushButton()
        self._btn_font_down.setIcon(icon_font_decrease(icon_color, 32))
        self._btn_font_down.setToolTip("Reducir tamaño de fuente")
        self._btn_font_down.setFixedSize(34, 34)
        toolbar.addWidget(self._btn_font_up)
        toolbar.addWidget(self._btn_font_down)

        # --- Central widget ---
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(12)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title_label = QLabel("DocScan Studio")
        title_label.setProperty("cssClass", "title")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Selecciona una aplicación para comenzar")
        subtitle_label.setProperty("cssClass", "subtitle")
        header_layout.addWidget(subtitle_label)

        layout.addLayout(header_layout)

        # Barra de búsqueda
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Buscar aplicaciones...")
        self._filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self._filter_edit)

        # Lista de aplicaciones (cards)
        self._app_list = AppListWidget()
        layout.addWidget(self._app_list, stretch=1)

        # Info de la app seleccionada
        self._info_label = QLabel("")
        self._info_label.setProperty("cssClass", "info")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Estado inicial de botones
        self._update_button_state()

    def _connect_signals(self) -> None:
        self._btn_new.clicked.connect(self._on_new_app)
        self._btn_open.clicked.connect(self._on_open_app)
        self._btn_configure.clicked.connect(self._on_configure_app)
        self._btn_delete.clicked.connect(self._on_delete_app)
        self._btn_refresh.clicked.connect(self._load_apps)
        self._btn_batch_manager.clicked.connect(self.batch_manager_requested.emit)
        self._btn_theme.clicked.connect(self._on_toggle_theme)
        self._btn_font_up.clicked.connect(self._theme_manager.increase_font)
        self._btn_font_down.clicked.connect(self._theme_manager.decrease_font)
        self._filter_edit.textChanged.connect(self._app_list.filter_apps)
        self._app_list.currentItemChanged.connect(self._on_selection_changed)
        self._app_list.itemDoubleClicked.connect(self._on_open_app)
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Tema
    # ------------------------------------------------------------------

    def _on_toggle_theme(self) -> None:
        """Alterna entre tema claro y oscuro."""
        self._theme_manager.toggle_theme()

    def _on_theme_changed(self, _theme_name: str) -> None:
        """Actualiza el botón de tema cuando cambia."""
        self._update_theme_button()
        self._update_font_icons()
        # Forzar repintado de la lista para actualizar colores del delegate
        self._app_list.viewport().update()

    def _update_theme_button(self) -> None:
        from app.ui.icon_factory import icon_moon, icon_sun
        if self._theme_manager.is_dark:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_sun())
        else:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_moon("#5c5f77"))

    def _update_font_icons(self) -> None:
        from app.ui.icon_factory import icon_font_decrease, icon_font_increase
        color = "#cdd6f4" if self._theme_manager.is_dark else "#4c4f69"
        self._btn_font_up.setIcon(icon_font_increase(color, 32))
        self._btn_font_down.setIcon(icon_font_decrease(color, 32))

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def _load_apps(self) -> None:
        """Carga la lista de aplicaciones desde la BD."""
        from app.db.repositories.application_repo import ApplicationRepository

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            apps = repo.get_all()
            self._app_list.populate(apps)

        count = self._app_list.count()
        self._status_bar.showMessage(
            f"{count} aplicación(es) disponible(s)", 3000,
        )
        self._update_button_state()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_new_app(self) -> None:
        """Crea una nueva aplicación."""
        from app.ui.launcher.new_app_dialog import NewAppDialog

        dialog = NewAppDialog(self)
        if dialog.exec():
            name = dialog.app_name()
            description = dialog.app_description()
            self._create_app(name, description)

    def _create_app(self, name: str, description: str) -> None:
        from app.db.repositories.application_repo import ApplicationRepository
        from app.models.application import Application

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            if repo.get_by_name(name):
                QMessageBox.warning(
                    self, "Error",
                    f"Ya existe una aplicación con el nombre '{name}'.",
                )
                return
            app = Application(name=name, description=description)
            repo.save(app)
            session.commit()

        self._load_apps()
        self._status_bar.showMessage(f"Aplicación '{name}' creada", 3000)

    def _on_open_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        if app_id is not None:
            log.info("Abriendo aplicación %d", app_id)
            self.app_opened.emit(app_id)

    def _on_configure_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        if app_id is not None:
            log.info("Configurar aplicación %d", app_id)
            self.app_configure.emit(app_id)

    def _on_delete_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        app_name = self._app_list.selected_app_name()
        if app_id is None:
            return

        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar la aplicación '{app_name}' y todos sus lotes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from app.db.repositories.application_repo import ApplicationRepository

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            repo.delete(app_id)
            session.commit()

        self._load_apps()
        self._status_bar.showMessage(f"Aplicación '{app_name}' eliminada", 3000)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        self._update_button_state()
        app_data = self._app_list.selected_app_data()
        if app_data:
            desc = app_data.get("description", "")
            desc_text = f" — {desc}" if desc else ""
            created = app_data.get("created_at", "")[:10]
            status = "Activa" if app_data.get("active", True) else "Inactiva"
            self._info_label.setText(
                f"<b>{app_data['name']}</b>{desc_text} · "
                f"{status} · Creada: {created}"
            )
        else:
            self._info_label.setText("")

    def _update_button_state(self) -> None:
        has_selection = self._app_list.selected_app_id() is not None
        self._btn_open.setEnabled(has_selection)
        self._btn_configure.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection)
