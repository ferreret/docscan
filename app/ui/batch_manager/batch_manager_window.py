"""Ventana del Gestor de Lotes.

Interfaz de histórico de lotes con filtros, lista, panel de detalle
y posibilidad de reabrir cualquier lote en el workbench.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
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
from app.services.batch_service import BatchService
from app.ui.batch_manager.batch_detail_panel import BatchDetailPanel
from app.ui.batch_manager.batch_list_widget import BatchListWidget
from config.settings import APP_IMAGES_DIR

log = logging.getLogger(__name__)

# Intervalo de refresco por defecto (ms)
DEFAULT_REFRESH_INTERVAL = 20_000


class BatchManagerWindow(QMainWindow):
    """Ventana principal del gestor de lotes (histórico).

    Args:
        session_factory: Fábrica de sesiones SQLAlchemy.
        parent: Widget padre.

    Signals:
        closed: Emitida al cerrar la ventana.
        open_batch_requested: Emitida para abrir un lote (app_id, batch_id).
    """

    closed = Signal()
    open_batch_requested = Signal(int, int)  # (app_id, batch_id)

    def __init__(
        self,
        session_factory: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._session_factory = session_factory
        self._selected_batch_id: int | None = None

        # Cache de apps para filtro
        self._apps_cache: dict[int, str] = {}

        self._setup_ui()
        self._connect_signals()
        self._load_filter_data()
        self._refresh_batches()

        # Auto-refresco
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_batches)
        self._refresh_timer.start(DEFAULT_REFRESH_INTERVAL)

    # ==================================================================
    # Inicialización UI
    # ==================================================================

    def _setup_ui(self) -> None:
        """Construye la interfaz completa."""
        self.setWindowTitle(self.tr("DocScan Studio — Histórico de Lotes"))
        self.setMinimumSize(1000, 600)

        # --- Toolbar ---
        self._create_toolbar()

        # --- Layout principal con splitter ---
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Filtros (tamaño fijo, no crece)
        filter_bar = self._create_filter_bar()
        main_layout.addWidget(filter_bar, stretch=0)

        # Splitter: lista + detalle (ocupa todo el espacio restante)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._batch_list = BatchListWidget()
        self._detail_panel = BatchDetailPanel()

        self._splitter.addWidget(self._batch_list)
        self._splitter.addWidget(self._detail_panel)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self._splitter, stretch=1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._lbl_count = QLabel(self.tr("0 lotes"))
        self._status_bar.addPermanentWidget(self._lbl_count)

    def _create_toolbar(self) -> None:
        """Barra de herramientas con acciones."""
        toolbar = QToolBar(self.tr("Lotes"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._btn_open_batch = QPushButton(self.tr("Abrir lote"))
        self._btn_open_batch.setProperty("cssClass", "primary")
        self._btn_refresh = QPushButton(self.tr("Actualizar"))
        self._btn_delete = QPushButton(self.tr("Eliminar"))
        self._btn_delete.setProperty("cssClass", "danger")

        toolbar.addWidget(self._btn_open_batch)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_refresh)
        toolbar.addSeparator()
        toolbar.addWidget(self._btn_delete)

    def _create_filter_bar(self) -> QWidget:
        """Barra de filtros."""
        widget = QWidget()
        widget.setFixedHeight(44)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Aplicación
        layout.addWidget(QLabel(self.tr("Aplicación:")))
        self._combo_app = QComboBox()
        self._combo_app.addItem(self.tr("Todas"), 0)
        self._combo_app.setMinimumWidth(150)
        layout.addWidget(self._combo_app)

        # Estación
        layout.addWidget(QLabel(self.tr("Estación:")))
        self._combo_hostname = QComboBox()
        self._combo_hostname.addItem(self.tr("Todas"), "")
        self._combo_hostname.setMinimumWidth(120)
        layout.addWidget(self._combo_hostname)

        # Fechas
        today = QDate.currentDate()

        layout.addWidget(QLabel(self.tr("Desde:")))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(today.addDays(-30))
        self._date_from.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self._date_from)

        layout.addWidget(QLabel(self.tr("Hasta:")))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(today)
        self._date_to.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self._date_to)

        self._btn_filter = QPushButton(self.tr("Filtrar"))
        layout.addWidget(self._btn_filter)

        layout.addStretch()
        return widget

    def _connect_signals(self) -> None:
        """Conecta señales de la UI."""
        self._batch_list.batch_selected.connect(self._on_batch_selected)
        self._batch_list.batch_double_clicked.connect(self._on_open_batch)
        self._btn_open_batch.clicked.connect(self._on_open_batch)
        self._btn_refresh.clicked.connect(self._refresh_batches)
        self._btn_filter.clicked.connect(self._refresh_batches)
        self._btn_delete.clicked.connect(self._on_delete)

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
        # Evitar refrescos del timer cuando la ventana no es visible,
        # pero permitir la carga inicial (sender() es None)
        if not self.isVisible() and self.sender() is not None:
            return

        app_id = self._combo_app.currentData() or None
        hostname = self._combo_hostname.currentData() or None

        date_from = self._qdate_to_datetime(self._date_from.date())
        date_to = self._qdate_to_datetime(self._date_to.date(), end_of_day=True)

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            batches = batch_repo.get_filtered(
                state=None,
                application_id=app_id,
                hostname=hostname,
                date_from=date_from,
                date_to=date_to,
            )

            batch_dicts = []
            for b in batches:
                batch_dicts.append({
                    "id": b.id,
                    "application_id": b.application_id,
                    "app_name": self._apps_cache.get(b.application_id, f"App {b.application_id}"),
                    "state": b.state,
                    "page_count": b.page_count,
                    "hostname": b.hostname,
                    "created_at": b.created_at,
                    "updated_at": b.updated_at,
                })

        self._batch_app_map = {b["id"]: b["application_id"] for b in batch_dicts}
        self._batch_list.set_batches(batch_dicts)
        self._lbl_count.setText(self.tr("{0} lote(s)").format(len(batch_dicts)))

        # Re-seleccionar fila si había un lote seleccionado
        if self._selected_batch_id is not None:
            ids = self._batch_list._batch_ids
            if self._selected_batch_id in ids:
                self._batch_list.selectRow(ids.index(self._selected_batch_id))

    @staticmethod
    def _qdate_to_datetime(qdate: QDate, end_of_day: bool = False) -> datetime:
        """Convierte QDate a datetime."""
        t = (23, 59, 59) if end_of_day else (0, 0, 0)
        return datetime(qdate.year(), qdate.month(), qdate.day(), *t)

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

            # Páginas (una sola query, derivar stats en memoria)
            pages = page_repo.get_by_batch(batch_id)
            stats = {
                "total_pages": len(pages),
                "needs_review": sum(1 for p in pages if p.needs_review),
                "excluded": sum(1 for p in pages if p.is_excluded),
                "blank": sum(1 for p in pages if p.is_blank),
                "with_errors": sum(
                    1 for p in pages if p.processing_errors_json != "[]"
                ),
            }
            self._detail_panel.set_stats(stats, batch.stats_json)

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

    def _require_selected_batch(self) -> int | None:
        """Devuelve el batch_id seleccionado o muestra aviso."""
        batch_id = self._batch_list.get_selected_batch_id()
        if batch_id is None:
            QMessageBox.information(self, self.tr("Sin selección"), self.tr("Selecciona un lote."))
        return batch_id

    def _on_open_batch(self) -> None:
        """Abre el lote seleccionado en el workbench."""
        batch_id = self._require_selected_batch()
        if batch_id is None:
            return

        app_id = self._batch_app_map.get(batch_id)
        if app_id is None:
            return

        self.open_batch_requested.emit(app_id, batch_id)

    def _on_delete(self) -> None:
        """Eliminar el lote seleccionado."""
        batch_id = self._require_selected_batch()
        if batch_id is None:
            return

        reply = QMessageBox.question(
            self, self.tr("Confirmar eliminación"),
            self.tr("¿Eliminar el lote {0} y sus imágenes de disco?\nEsta acción no se puede deshacer.").format(batch_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        with self._session_factory() as session:
            batch_svc = BatchService(session, APP_IMAGES_DIR)
            batch_svc.delete_batch(batch_id)
            session.commit()

        self._selected_batch_id = None
        self._detail_panel.clear_all()
        self._refresh_batches()
        self._status_bar.showMessage(self.tr("Lote {0} eliminado").format(batch_id), 5000)

    # ==================================================================
    # Cierre
    # ==================================================================

    def closeEvent(self, event) -> None:
        """Detiene el timer de refresco y emite closed."""
        self._refresh_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
        self.deleteLater()
