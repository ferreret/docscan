"""Ventana principal del Launcher.

Lista las aplicaciones disponibles y permite abrir, crear,
configurar o eliminar aplicaciones.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
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
        self.setWindowTitle(self.tr("DocScan Studio"))
        self.setMinimumSize(900, 600)

        # --- Layout principal: sidebar + contenido ---
        central = QWidget()
        self.setCentralWidget(central)
        main_hlayout = QHBoxLayout(central)
        main_hlayout.setContentsMargins(0, 0, 0, 0)
        main_hlayout.setSpacing(0)

        # Sidebar izquierdo
        from app.ui.launcher.sidebar import Sidebar

        self._sidebar = Sidebar(
            is_dark=self._theme_manager.is_dark, parent=self,
        )
        self._sidebar.action_triggered.connect(self._on_sidebar_action)
        main_hlayout.addWidget(self._sidebar)

        # Contenido derecho con splitter (lista + AI mode)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        main_hlayout.addWidget(self._splitter, 1)

        # Panel principal del launcher
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(10)

        # Header con titulo + controles de aspecto
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_left = QVBoxLayout()
        header_left.setSpacing(2)
        title_label = QLabel(self.tr("DocScan Studio"))
        title_label.setProperty("cssClass", "title")
        header_left.addWidget(title_label)
        subtitle_label = QLabel(self.tr("Selecciona una aplicación para comenzar"))
        subtitle_label.setProperty("cssClass", "subtitle")
        header_left.addWidget(subtitle_label)
        header_row.addLayout(header_left, 1)

        # Controles de aspecto (tema, fuente, idioma) en el header
        from app.ui.icon_factory import icon_font_decrease, icon_font_increase

        self._btn_theme = QPushButton()
        self._btn_theme.setToolTip(self.tr("Cambiar tema claro/oscuro"))
        self._btn_theme.setFixedSize(34, 34)
        self._update_theme_button()
        header_row.addWidget(self._btn_theme)

        icon_color = "#cdd6f4" if self._theme_manager.is_dark else "#4c4f69"

        self._btn_font_up = QPushButton()
        self._btn_font_up.setIcon(icon_font_increase(icon_color, 32))
        self._btn_font_up.setToolTip(self.tr("Aumentar tamaño de fuente"))
        self._btn_font_up.setFixedSize(34, 34)
        self._btn_font_down = QPushButton()
        self._btn_font_down.setIcon(icon_font_decrease(icon_color, 32))
        self._btn_font_down.setToolTip(self.tr("Reducir tamaño de fuente"))
        self._btn_font_down.setFixedSize(34, 34)
        header_row.addWidget(self._btn_font_up)
        header_row.addWidget(self._btn_font_down)

        from app.i18n import available_languages, get_language_preference

        self._lang_combo = QComboBox()
        self._lang_combo.setFixedWidth(60)
        self._lang_combo.blockSignals(True)
        for code, name in available_languages().items():
            self._lang_combo.addItem(name, code)
        idx = self._lang_combo.findData(get_language_preference())
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.blockSignals(False)
        header_row.addWidget(self._lang_combo)

        layout.addLayout(header_row)

        # Barra de búsqueda
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(self.tr("Buscar aplicaciones..."))
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

        self._splitter.addWidget(left_panel)

        # Panel AI MODE (oculto por defecto)
        from app.ui.launcher.ai_mode_panel import AiModePanel

        self._ai_mode_panel = AiModePanel(self._session_factory)
        self._ai_mode_panel.setVisible(False)
        self._ai_mode_panel.apps_changed.connect(self._load_apps)
        self._splitter.addWidget(self._ai_mode_panel)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Estado inicial de botones
        self._update_button_state()

    def _connect_signals(self) -> None:
        # Sidebar ya conectado via action_triggered en _setup_ui
        self._btn_theme.clicked.connect(self._on_toggle_theme)
        self._btn_font_up.clicked.connect(self._theme_manager.increase_font)
        self._btn_font_down.clicked.connect(self._theme_manager.decrease_font)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self._filter_edit.textChanged.connect(self._app_list.filter_apps)
        self._app_list.currentItemChanged.connect(self._on_selection_changed)
        self._app_list.itemDoubleClicked.connect(self._on_open_app)
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Sidebar dispatch
    # ------------------------------------------------------------------

    def _on_sidebar_action(self, action: str) -> None:
        """Despacha la accion del sidebar al metodo correspondiente."""
        handlers = {
            "new": self._on_new_app,
            "open": self._on_open_app,
            "configure": self._on_configure_app,
            "clone": self._on_clone_app,
            "export": self._on_export_app,
            "import": self._on_import_app,
            "delete": self._on_delete_app,
            "refresh": self._load_apps,
            "batch_manager": self.batch_manager_requested.emit,
            "ai_mode": self._on_toggle_ai_mode,
        }
        handler = handlers.get(action)
        if handler:
            handler()

    def _on_toggle_ai_mode(self) -> None:
        """Muestra u oculta el panel AI MODE."""
        btn = self._sidebar.get_button("ai_mode")
        checked = btn.isChecked() if btn else False
        self._ai_mode_panel.setVisible(checked)

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
        self._sidebar.update_theme(self._theme_manager.is_dark)
        self._app_list.viewport().update()

    def _on_language_changed(self, _index: int) -> None:
        """Cambia el idioma de la aplicación."""
        lang_code = self._lang_combo.currentData()
        if not lang_code:
            return

        from app.i18n import load_language, save_language_preference

        save_language_preference(lang_code)
        load_language(lang_code)

        QMessageBox.information(
            self, self.tr("Idioma cambiado"),
            self.tr("El idioma se aplicará completamente al reiniciar la aplicación."),
        )

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
            self.tr("{0} aplicación(es) disponible(s)").format(count), 3000,
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
                    self, self.tr("Error"),
                    self.tr("Ya existe una aplicación con el nombre '{0}'.").format(name),
                )
                return
            app = Application(name=name, description=description)
            repo.save(app)
            session.commit()

        self._load_apps()
        self._status_bar.showMessage(self.tr("Aplicación '{0}' creada").format(name), 3000)

    def _on_open_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        if app_id is None:
            return
        app_data = self._app_list.selected_app_data()
        if app_data and not app_data.get("active", True):
            QMessageBox.information(
                self, self.tr("Aplicación inactiva"),
                self.tr("Esta aplicación está inactiva. Actívala desde "
                "el configurador antes de abrirla."),
            )
            return
        log.info("Abriendo aplicación %d", app_id)
        self.app_opened.emit(app_id)

    def _on_configure_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        if app_id is not None:
            log.info("Configurar aplicación %d", app_id)
            self.app_configure.emit(app_id)

    def _on_clone_app(self) -> None:
        """Clona la aplicación seleccionada."""
        app_id = self._app_list.selected_app_id()
        if app_id is None:
            return

        from app.db.repositories.application_repo import ApplicationRepository
        from app.models.application import Application

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            original = repo.get_by_id(app_id)
            if original is None:
                return

            # Generar nombre único (una sola query)
            existing_names = {a.name for a in repo.get_all()}
            clone_name = f"{original.name} (copia)"
            counter = 2
            while clone_name in existing_names:
                clone_name = f"{original.name} (copia {counter})"
                counter += 1

            clone = Application(
                name=clone_name,
                description=original.description,
                active=original.active,
                pipeline_json=original.pipeline_json,
                events_json=original.events_json,
                transfer_json=original.transfer_json,
                batch_fields_json=original.batch_fields_json,
                index_fields_json=original.index_fields_json,
                auto_transfer=original.auto_transfer,
                close_after_transfer=original.close_after_transfer,
                background_color=original.background_color,
                output_format=original.output_format,
                default_tab=original.default_tab,
                scanner_backend=original.scanner_backend,
                image_config_json=original.image_config_json,
                ai_config_json=original.ai_config_json,
            )
            repo.save(clone)
            session.commit()

        self._load_apps()
        self._status_bar.showMessage(self.tr("Aplicación clonada como '{0}'").format(clone_name), 3000)

    def _on_export_app(self) -> None:
        """Exporta la aplicación seleccionada a un fichero .docscan."""
        app_id = self._app_list.selected_app_id()
        if app_id is None:
            return

        from PySide6.QtWidgets import QFileDialog
        from app.db.repositories.application_repo import ApplicationRepository

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_id(app_id)
            if app is None:
                return

            safe_name = app.name.replace(" ", "_").replace("/", "_")
            path, _ = QFileDialog.getSaveFileName(
                self,
                self.tr("Exportar aplicación"),
                f"{safe_name}.docscan",
                self.tr("DocScan App (*.docscan)"),
            )
            if not path:
                return

            try:
                from app.services.app_export_service import export_to_file
                export_to_file(app, path)
                self._status_bar.showMessage(
                    self.tr("Aplicación '{0}' exportada").format(app.name), 3000,
                )
            except Exception as e:
                QMessageBox.critical(
                    self, self.tr("Error al exportar"), str(e),
                )

    def _on_import_app(self) -> None:
        """Importa una aplicación desde un fichero .docscan."""
        import json
        from PySide6.QtWidgets import QFileDialog
        from app.services.app_export_service import (
            AppImportError,
            import_application,
            validate_import_data,
        )

        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Importar aplicación"),
            "",
            self.tr("DocScan App (*.docscan);;JSON (*.json)"),
        )
        if not path:
            return

        try:
            from pathlib import Path
            text = Path(path).read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error al leer fichero"), str(e),
            )
            return

        errors = validate_import_data(data)
        if errors:
            QMessageBox.warning(
                self, self.tr("Fichero no válido"),
                "\n".join(errors),
            )
            return

        try:
            with self._session_factory() as session:
                app = import_application(data, session)
                session.commit()
            self._load_apps()
            self._status_bar.showMessage(
                self.tr("Aplicación '{0}' importada").format(app.name), 3000,
            )
        except AppImportError as e:
            QMessageBox.warning(
                self, self.tr("Error de importación"), str(e),
            )
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error al importar"), str(e),
            )

    def _on_delete_app(self) -> None:
        app_id = self._app_list.selected_app_id()
        app_name = self._app_list.selected_app_name()
        if app_id is None:
            return

        reply = QMessageBox.question(
            self, self.tr("Confirmar eliminación"),
            self.tr("¿Eliminar la aplicación '{0}' y todos sus lotes?").format(app_name),
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
        self._status_bar.showMessage(self.tr("Aplicación '{0}' eliminada").format(app_name), 3000)

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
            status = self.tr("Activa") if app_data.get("active", True) else self.tr("Inactiva")
            self._info_label.setText(
                f"<b>{app_data['name']}</b>{desc_text} · "
                f"{status} · Creada: {created}"
            )
        else:
            self._info_label.setText("")

    def _update_button_state(self) -> None:
        has_selection = self._app_list.selected_app_id() is not None
        for name in ("open", "configure", "clone", "export", "delete"):
            self._sidebar.set_button_enabled(name, has_selection)
