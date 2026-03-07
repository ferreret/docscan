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
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.launcher.app_list_widget import AppListWidget

log = logging.getLogger(__name__)


class LauncherWindow(QMainWindow):
    """Ventana principal del launcher de DocScan Studio.

    Signals:
        app_opened: Emitida cuando el usuario abre una aplicación (app_id).
        app_configure: Emitida cuando se quiere configurar una app (app_id).
    """

    app_opened = Signal(int)
    app_configure = Signal(int)

    def __init__(self, session_factory: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._setup_ui()
        self._connect_signals()
        self._load_apps()

    def _setup_ui(self) -> None:
        self.setWindowTitle("DocScan Studio")
        self.setMinimumSize(700, 500)

        # --- Toolbar ---
        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._btn_new = QPushButton("Nueva")
        self._btn_open = QPushButton("Abrir")
        self._btn_configure = QPushButton("Configurar")
        self._btn_delete = QPushButton("Eliminar")
        self._btn_refresh = QPushButton("Actualizar")

        toolbar.addWidget(self._btn_new)
        toolbar.addWidget(self._btn_open)
        toolbar.addWidget(self._btn_configure)
        toolbar.addWidget(self._btn_delete)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_refresh)

        # --- Central widget ---
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Filtro de búsqueda
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Buscar:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filtrar aplicaciones...")
        self._filter_edit.setClearButtonEnabled(True)
        filter_layout.addWidget(self._filter_edit)
        layout.addLayout(filter_layout)

        # Lista de aplicaciones
        self._app_list = AppListWidget()
        layout.addWidget(self._app_list)

        # Info de la app seleccionada
        self._info_label = QLabel("")
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
        self._filter_edit.textChanged.connect(self._app_list.filter_apps)
        self._app_list.currentItemChanged.connect(self._on_selection_changed)
        self._app_list.itemDoubleClicked.connect(self._on_open_app)

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

        self._status_bar.showMessage(
            f"{self._app_list.count()} aplicación(es)", 3000,
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
            self._info_label.setText(
                f"<b>{app_data['name']}</b><br>"
                f"{app_data.get('description', '')}<br>"
                f"<small>Creada: {app_data.get('created_at', '')}</small>"
            )
        else:
            self._info_label.setText("")

    def _update_button_state(self) -> None:
        has_selection = self._app_list.selected_app_id() is not None
        self._btn_open.setEnabled(has_selection)
        self._btn_configure.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection)
