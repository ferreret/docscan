"""Ventana del Gestor de Lotes (BAT-04 a BAT-10).

Interfaz de gestión de lotes con filtros, lista coloreada por estado,
panel de detalle con pestañas, modo supervisor y refresco automático.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from getpass import getuser
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.db.repositories.application_repo import ApplicationRepository
from app.db.repositories.batch_repo import BatchRepository
from app.db.repositories.operation_history_repo import OperationHistoryRepository
from app.db.repositories.page_repo import PageRepository
from app.models.batch import BATCH_STATES
from app.models.operation_history import OperationHistory
from app.services.batch_service import BatchService
from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel
from app.ui.batch_manager.batch_list_widget import BatchListWidget, STATE_LABELS
from config.settings import APP_DATA_DIR

log = logging.getLogger(__name__)

# Transiciones válidas en modo usuario
VALID_TRANSITIONS: dict[str, list[str]] = {
    "created": ["read"],
    "read": ["verified", "error_read"],
    "verified": ["ready_to_export"],
    "ready_to_export": ["exported", "error_export"],
    "error_read": ["read"],
    "error_export": ["ready_to_export"],
}

# Contraseña supervisor por defecto (debería ser configurable)
SUPERVISOR_PASSWORD = "supervisor"

# Intervalo de refresco por defecto (ms)
DEFAULT_REFRESH_INTERVAL = 20_000


class BatchManagerWindow(QMainWindow):
    """Ventana principal del gestor de lotes.

    Args:
        session_factory: Fábrica de sesiones SQLAlchemy.
        parent: Widget padre.

    Signals:
        closed: Emitida al cerrar la ventana.
    """

    closed = Signal()

    def __init__(
        self,
        session_factory: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._supervisor_mode = False
        self._selected_batch_id: int | None = None

        # Cache de apps para filtro
        self._apps_cache: dict[int, str] = {}

        self._setup_ui()
        self._connect_signals()
        self._load_filter_data()
        self._refresh_batches()

        # Auto-refresco (BAT-07)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_batches)
        self._refresh_timer.start(DEFAULT_REFRESH_INTERVAL)

    # ==================================================================
    # Inicialización UI
    # ==================================================================

    def _setup_ui(self) -> None:
        """Construye la interfaz completa."""
        self.setWindowTitle("DocScan Studio — Gestor de Lotes")
        self.setMinimumSize(1000, 600)

        # --- Toolbar ---
        self._create_toolbar()

        # --- Layout principal con splitter ---
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Filtros
        main_layout.addWidget(self._create_filter_bar())

        # Splitter: lista + detalle
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._batch_list = BatchListWidget()
        self._detail_panel = BatchDetailPanel()

        self._splitter.addWidget(self._batch_list)
        self._splitter.addWidget(self._detail_panel)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self._splitter)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._lbl_count = QLabel("0 lotes")
        self._status_bar.addPermanentWidget(self._lbl_count)

    def _create_toolbar(self) -> None:
        """Barra de herramientas con acciones."""
        toolbar = QToolBar("Lotes")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._btn_refresh = QPushButton("Actualizar")
        self._btn_transition = QPushButton("Cambiar estado")
        self._btn_reprocess = QPushButton("Re-procesar errores")
        self._btn_delete = QPushButton("Eliminar")
        self._btn_supervisor = QPushButton("Modo Supervisor")
        self._btn_supervisor.setCheckable(True)

        toolbar.addWidget(self._btn_refresh)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_transition)
        toolbar.addWidget(self._btn_reprocess)
        toolbar.addWidget(self._btn_delete)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_supervisor)

    def _create_filter_bar(self) -> QWidget:
        """Barra de filtros."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Estado
        layout.addWidget(QLabel("Estado:"))
        self._combo_state = QComboBox()
        self._combo_state.addItem("Todos", "")
        for state, label in STATE_LABELS.items():
            self._combo_state.addItem(label, state)
        self._combo_state.setMinimumWidth(130)
        layout.addWidget(self._combo_state)

        # Aplicación
        layout.addWidget(QLabel("Aplicación:"))
        self._combo_app = QComboBox()
        self._combo_app.addItem("Todas", 0)
        self._combo_app.setMinimumWidth(150)
        layout.addWidget(self._combo_app)

        # Estación
        layout.addWidget(QLabel("Estación:"))
        self._combo_hostname = QComboBox()
        self._combo_hostname.addItem("Todas", "")
        self._combo_hostname.setMinimumWidth(120)
        layout.addWidget(self._combo_hostname)

        # Fechas
        today = QDate.currentDate()

        layout.addWidget(QLabel("Desde:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(today.addDays(-30))
        self._date_from.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self._date_from)

        layout.addWidget(QLabel("Hasta:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(today)
        self._date_to.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self._date_to)

        self._btn_filter = QPushButton("Filtrar")
        layout.addWidget(self._btn_filter)

        layout.addStretch()
        return widget

    def _connect_signals(self) -> None:
        """Conecta señales de la UI."""
        self._batch_list.batch_selected.connect(self._on_batch_selected)
        self._btn_refresh.clicked.connect(self._refresh_batches)
        self._btn_filter.clicked.connect(self._refresh_batches)
        self._btn_transition.clicked.connect(self._on_transition)
        self._btn_reprocess.clicked.connect(self._on_reprocess_errors)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_supervisor.clicked.connect(self._on_toggle_supervisor)

    # ==================================================================
    # Carga de datos
    # ==================================================================

    def _load_filter_data(self) -> None:
        """Carga datos para los combos de filtro."""
        with self._session_factory() as session:
            # Aplicaciones
            app_repo = ApplicationRepository(session)
            apps = app_repo.get_all()
            self._apps_cache.clear()
            for app in apps:
                self._apps_cache[app.id] = app.name
                self._combo_app.addItem(app.name, app.id)

            # Hostnames
            batch_repo = BatchRepository(session)
            hostnames = batch_repo.get_distinct_hostnames()
            for h in hostnames:
                self._combo_hostname.addItem(h, h)

    def _refresh_batches(self) -> None:
        """Recarga la lista de lotes aplicando los filtros actuales."""
        # Leer filtros
        state = self._combo_state.currentData() or None
        app_id = self._combo_app.currentData() or None
        if app_id == 0:
            app_id = None
        hostname = self._combo_hostname.currentData() or None

        date_from = datetime(
            self._date_from.date().year(),
            self._date_from.date().month(),
            self._date_from.date().day(),
        )
        date_to = datetime(
            self._date_to.date().year(),
            self._date_to.date().month(),
            self._date_to.date().day(),
            23, 59, 59,
        )

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            batches = batch_repo.get_filtered(
                state=state,
                application_id=app_id,
                hostname=hostname,
                date_from=date_from,
                date_to=date_to,
            )

            batch_dicts = []
            for b in batches:
                batch_dicts.append({
                    "id": b.id,
                    "app_name": self._apps_cache.get(b.application_id, f"App {b.application_id}"),
                    "state": b.state,
                    "page_count": b.page_count,
                    "hostname": b.hostname,
                    "created_at": b.created_at,
                    "updated_at": b.updated_at,
                })

        self._batch_list.set_batches(batch_dicts)
        self._lbl_count.setText(f"{len(batch_dicts)} lote(s)")

        # Si había un lote seleccionado, intentar re-seleccionarlo
        if self._selected_batch_id is not None:
            self._on_batch_selected(self._selected_batch_id)

    # ==================================================================
    # Detalle del lote
    # ==================================================================

    def _on_batch_selected(self, batch_id: int) -> None:
        """Carga el detalle del lote seleccionado."""
        self._selected_batch_id = batch_id

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            page_repo = PageRepository(session)
            history_repo = OperationHistoryRepository(session)
            batch_svc = BatchService(session, APP_DATA_DIR / "images")

            batch = batch_repo.get_by_id(batch_id)
            if batch is None:
                self._detail_panel.clear_all()
                return

            # General
            self._detail_panel.set_general_info({
                "id": batch.id,
                "app_name": self._apps_cache.get(
                    batch.application_id, f"App {batch.application_id}",
                ),
                "state": batch.state,
                "hostname": batch.hostname,
                "username": batch.username,
                "page_count": batch.page_count,
                "created_at": batch.created_at,
                "updated_at": batch.updated_at,
                "folder_path": batch.folder_path,
            })

            # Estadísticas
            stats = batch_svc.get_stats(batch_id)
            self._detail_panel.set_stats(stats, batch.stats_json)

            # Páginas
            pages = page_repo.get_by_batch(batch_id)
            page_dicts = []
            for p in pages:
                errors = json.loads(p.processing_errors_json) if p.processing_errors_json != "[]" else []
                page_dicts.append({
                    "page_index": p.page_index,
                    "needs_review": p.needs_review,
                    "is_excluded": p.is_excluded,
                    "is_blank": p.is_blank,
                    "ocr_text": p.ocr_text,
                    "error_count": len(errors),
                })
            self._detail_panel.set_pages(page_dicts)

            # Historial
            history = history_repo.get_by_batch(batch_id)
            history_dicts = []
            for h in history:
                history_dicts.append({
                    "timestamp": h.timestamp,
                    "operation": h.operation,
                    "old_state": h.old_state,
                    "new_state": h.new_state,
                    "username": h.username,
                    "message": h.message,
                })
            self._detail_panel.set_history(history_dicts)

    # ==================================================================
    # Acciones
    # ==================================================================

    def _on_transition(self) -> None:
        """Cambiar estado del lote seleccionado."""
        batch_id = self._batch_list.get_selected_batch_id()
        if batch_id is None:
            QMessageBox.information(self, "Sin selección", "Selecciona un lote.")
            return

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            batch = batch_repo.get_by_id(batch_id)
            if batch is None:
                return

            current = batch.state

        # Determinar estados posibles
        if self._supervisor_mode:
            options = list(BATCH_STATES)
        else:
            options = VALID_TRANSITIONS.get(current, [])

        if not options:
            QMessageBox.information(
                self, "Sin transiciones",
                f"No hay transiciones válidas desde '{STATE_LABELS.get(current, current)}'.",
            )
            return

        labels = [STATE_LABELS.get(s, s) for s in options]
        chosen, ok = QInputDialog.getItem(
            self, "Cambiar estado",
            f"Estado actual: {STATE_LABELS.get(current, current)}\n"
            "Selecciona el nuevo estado:",
            labels, 0, False,
        )
        if not ok:
            return

        new_state = options[labels.index(chosen)]

        with self._session_factory() as session:
            batch_svc = BatchService(session, APP_DATA_DIR / "images")
            old_state = current
            batch_svc.transition_state(batch_id, new_state)

            # Registrar en historial
            history_repo = OperationHistoryRepository(session)
            entry = OperationHistory(
                batch_id=batch_id,
                operation="state_change",
                old_state=old_state,
                new_state=new_state,
                username=getuser(),
                message=f"{'Supervisor: ' if self._supervisor_mode else ''}Cambio de estado",
            )
            history_repo.add(entry)
            session.commit()

        self._refresh_batches()
        self._status_bar.showMessage(
            f"Lote {batch_id}: {STATE_LABELS.get(old_state, old_state)} → "
            f"{STATE_LABELS.get(new_state, new_state)}",
            5000,
        )

    def _on_reprocess_errors(self) -> None:
        """Re-procesar páginas con errores del lote seleccionado (BAT-10)."""
        batch_id = self._batch_list.get_selected_batch_id()
        if batch_id is None:
            QMessageBox.information(self, "Sin selección", "Selecciona un lote.")
            return

        with self._session_factory() as session:
            page_repo = PageRepository(session)
            pages = page_repo.get_needs_review(batch_id)

            if not pages:
                QMessageBox.information(
                    self, "Sin páginas",
                    "No hay páginas pendientes de revisión en este lote.",
                )
                return

            reply = QMessageBox.question(
                self, "Re-procesar",
                f"¿Re-procesar {len(pages)} página(s) con errores?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # Registrar operación
            history_repo = OperationHistoryRepository(session)
            entry = OperationHistory(
                batch_id=batch_id,
                operation="reprocess_errors",
                username=getuser(),
                message=f"Re-procesado de {len(pages)} página(s) con errores",
            )
            history_repo.add(entry)
            session.commit()

        self._status_bar.showMessage(
            f"Solicitud de re-procesado registrada para lote {batch_id}",
            5000,
        )

    def _on_delete(self) -> None:
        """Eliminar el lote seleccionado."""
        batch_id = self._batch_list.get_selected_batch_id()
        if batch_id is None:
            QMessageBox.information(self, "Sin selección", "Selecciona un lote.")
            return

        if not self._supervisor_mode:
            QMessageBox.warning(
                self, "Acceso denegado",
                "Se requiere modo Supervisor para eliminar lotes.",
            )
            return

        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el lote {batch_id} y sus imágenes de disco?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        with self._session_factory() as session:
            batch_svc = BatchService(session, APP_DATA_DIR / "images")
            batch_svc.delete_batch(batch_id)
            session.commit()

        self._selected_batch_id = None
        self._detail_panel.clear_all()
        self._refresh_batches()
        self._status_bar.showMessage(f"Lote {batch_id} eliminado", 5000)

    # ==================================================================
    # Modo Supervisor (BAT-05)
    # ==================================================================

    def _on_toggle_supervisor(self) -> None:
        """Activa/desactiva el modo supervisor."""
        if self._btn_supervisor.isChecked():
            password, ok = QInputDialog.getText(
                self, "Modo Supervisor",
                "Contraseña de supervisor:",
                echo=QLineEdit.EchoMode.Password,
            )
            if ok and password == SUPERVISOR_PASSWORD:
                self._supervisor_mode = True
                self._btn_supervisor.setStyleSheet(
                    "QPushButton { background-color: #FF8A80; font-weight: bold; }"
                )
                self._status_bar.showMessage("Modo Supervisor activado", 3000)
            else:
                self._btn_supervisor.setChecked(False)
                if ok:
                    QMessageBox.warning(
                        self, "Acceso denegado", "Contraseña incorrecta.",
                    )
        else:
            self._supervisor_mode = False
            self._btn_supervisor.setStyleSheet("")
            self._status_bar.showMessage("Modo Supervisor desactivado", 3000)

    # ==================================================================
    # Cierre
    # ==================================================================

    def closeEvent(self, event) -> None:
        """Detiene el timer de refresco y emite closed."""
        self._refresh_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
