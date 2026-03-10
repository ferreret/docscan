"""Ventana principal del Workbench (Módulo 4 — Interfaz de Explotación).

Orquesta los paneles (miniaturas, visor, barcodes, metadatos), los
workers (escaneo, reconocimiento, transferencia) y la navegación.
Nunca bloquea la UI: todo el trabajo pesado va en QThread.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.db.repositories.application_repo import ApplicationRepository
from app.db.repositories.page_repo import PageRepository
from app.models.application import Application
from app.models.barcode import Barcode
from app.models.page import Page
from app.pipeline.executor import PipelineExecutor
from app.pipeline.serializer import deserialize
from app.services.batch_service import BatchService
from app.services.image_pipeline import ImagePipelineService
from app.services.import_service import ImportService
from app.services.script_engine import ScriptEngine
from app.services.transfer_service import TransferService, parse_transfer_config
from app.ui.workbench.barcode_panel import BarcodePanel
from app.ui.workbench.document_viewer import DocumentViewer
from app.ui.workbench.metadata_panel import MetadataPanel
from app.ui.workbench.page_state import (
    PageState,
    determine_page_state,
)
from app.ui.workbench.thumbnail_panel import ThumbnailPanel
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    RecognitionWorker,
)
from app.workers.scan_worker import ScanWorker
from app.workers.transfer_worker import TransferWorker
from config.settings import APP_DATA_DIR

log = logging.getLogger(__name__)


class WorkbenchWindow(QMainWindow):
    """Ventana de explotación de una aplicación.

    Args:
        app_id: ID de la aplicación a abrir.
        session_factory: Fábrica de sesiones SQLAlchemy.
        parent: Widget padre.

    Signals:
        closed: Emitida al cerrar la ventana.
    """

    closed = Signal()

    def __init__(
        self,
        app_id: int,
        session_factory: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_id = app_id
        self._session_factory = session_factory

        # Estado interno
        self._application: Application | None = None
        self._batch_id: int | None = None
        self._pages: list[Page] = []
        self._current_page_index: int = -1

        # Servicios
        self._script_engine = ScriptEngine()
        self._image_service = ImagePipelineService()
        self._import_service = ImportService()
        self._transfer_service = TransferService()
        self._executor: PipelineExecutor | None = None

        # Workers
        self._scan_worker: ScanWorker | None = None
        self._recognition_worker: RecognitionWorker | None = None
        self._transfer_worker: TransferWorker | None = None

        # Inicializar
        self._load_application()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._create_batch()
        self._fire_event("on_app_start")

    # ==================================================================
    # Inicialización
    # ==================================================================

    def _load_application(self) -> None:
        """Carga la aplicación desde BD y prepara el executor."""
        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_id(self._app_id)
            if app is None:
                raise ValueError(f"Aplicación {self._app_id} no encontrada")
            session.expunge(app)
            self._application = app

        # Parsear y compilar pipeline
        try:
            steps = deserialize(self._application.pipeline_json)
        except Exception as e:
            log.error("Error deserializando pipeline: %s", e)
            steps = []

        # Compilar scripts del pipeline
        for step in steps:
            if step.type == "script":
                try:
                    self._script_engine.compile_step(step)
                except Exception as e:
                    log.warning("Error compilando script '%s': %s", step.id, e)

        # Compilar eventos
        self._compile_events()

        # Crear executor (barcode/ocr/ai opcionales por ahora)
        self._executor = PipelineExecutor(
            steps=steps,
            image_service=self._image_service,
            script_engine=self._script_engine,
        )

    def _compile_events(self) -> None:
        """Pre-compila los scripts de eventos del ciclo de vida."""
        try:
            events = json.loads(self._application.events_json)
        except (json.JSONDecodeError, TypeError):
            events = {}

        for event_name, source in events.items():
            if source and source.strip():
                try:
                    self._script_engine.compile_script(
                        event_name, source, label=event_name,
                    )
                except Exception as e:
                    log.warning(
                        "Error compilando evento '%s': %s", event_name, e,
                    )

    def _setup_ui(self) -> None:
        """Construye toda la interfaz gráfica."""
        app_name = self._application.name if self._application else "Workbench"
        self.setWindowTitle(f"DocScan Studio — {app_name}")
        self.setMinimumSize(1024, 700)

        # Color de fondo personalizado (APP-04)
        if self._application and self._application.background_color:
            self.setStyleSheet(
                f"QMainWindow {{ background-color: "
                f"{self._application.background_color}; }}"
            )

        # --- Toolbar ---
        self._create_toolbar()

        # --- Layout principal con splitter ---
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: miniaturas + botones
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._thumbnail_panel = ThumbnailPanel()
        left_layout.addWidget(self._thumbnail_panel)
        left_layout.addWidget(self._create_action_buttons())

        # Panel central: visor + barra de origen
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self._viewer = DocumentViewer()
        center_layout.addWidget(self._viewer, stretch=1)
        center_layout.addWidget(self._create_source_bar())

        # Panel derecho: barcodes + metadatos
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._barcode_panel = BarcodePanel()
        self._metadata_panel = MetadataPanel()

        right_layout.addWidget(self._barcode_panel, stretch=1)
        right_layout.addWidget(self._metadata_panel, stretch=2)

        # Armar splitter
        self._splitter.addWidget(left_widget)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 1)  # ~15%
        self._splitter.setStretchFactor(1, 4)  # ~55%
        self._splitter.setStretchFactor(2, 2)  # ~30%

        main_layout.addWidget(self._splitter)

        # --- Status bar con barra de progreso ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

        # Configurar metadatos
        self._configure_metadata()

        # Pestaña por defecto (APP-07)
        if self._application:
            self._metadata_panel.set_default_tab(
                self._application.default_tab or "lote",
            )

    def _create_toolbar(self) -> None:
        """Crea la barra de herramientas principal."""
        toolbar = QToolBar("Workbench")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Procesar / Transferir
        self._btn_process = QPushButton("Procesar")
        self._btn_transfer = QPushButton("Transferir")
        toolbar.addWidget(self._btn_process)
        toolbar.addWidget(self._btn_transfer)
        toolbar.addSeparator()

        # Navegación (UI-09)
        self._btn_first = QPushButton("|<")
        self._btn_prev = QPushButton("<")
        self._btn_next = QPushButton(">")
        self._btn_last = QPushButton(">|")
        self._lbl_page_info = QLabel(" 0 / 0 ")

        toolbar.addWidget(self._btn_first)
        toolbar.addWidget(self._btn_prev)
        toolbar.addWidget(self._lbl_page_info)
        toolbar.addWidget(self._btn_next)
        toolbar.addWidget(self._btn_last)
        toolbar.addSeparator()

        # Navegación inteligente
        self._btn_next_barcode = QPushButton("BC>")
        self._btn_next_barcode.setToolTip("Siguiente con barcode")
        self._btn_next_review = QPushButton("R>")
        self._btn_next_review.setToolTip("Siguiente con revisión")
        toolbar.addWidget(self._btn_next_barcode)
        toolbar.addWidget(self._btn_next_review)
        toolbar.addSeparator()

        # Manipulación (UI-07)
        self._btn_mark = QPushButton("Marcar")
        self._btn_mark.setToolTip("Marcar/desmarcar página (excluir)")
        self._btn_rotate = QPushButton("Rotar 90°")
        self._btn_delete_from = QPushButton("Borrar desde aquí")

        toolbar.addWidget(self._btn_mark)
        toolbar.addWidget(self._btn_rotate)
        toolbar.addWidget(self._btn_delete_from)

    def _create_action_buttons(self) -> QWidget:
        """Botones de acción bajo las miniaturas."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)

        self._btn_insert_bc = QPushButton("+ Barcode manual")
        self._btn_delete_bc = QPushButton("- Barcode")

        layout.addWidget(self._btn_insert_bc)
        layout.addWidget(self._btn_delete_bc)
        return widget

    def _create_source_bar(self) -> QWidget:
        """Barra de origen: escáner o importar (UI-05, UI-13)."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self._radio_scanner = QRadioButton("Escáner")
        self._radio_import = QRadioButton("Importar")
        self._radio_import.setChecked(True)

        self._combo_source = QComboBox()
        self._combo_source.setMinimumWidth(200)
        self._combo_source.setEditable(False)
        self._combo_source.setPlaceholderText("Seleccionar origen...")

        self._btn_scan = QPushButton("Escanear / Importar")

        layout.addWidget(self._radio_scanner)
        layout.addWidget(self._radio_import)
        layout.addWidget(self._combo_source)
        layout.addStretch()
        layout.addWidget(self._btn_scan)

        return widget

    def _connect_signals(self) -> None:
        """Conecta todas las señales de la UI."""
        # Procesar / Transferir
        self._btn_process.clicked.connect(self._on_process)
        self._btn_transfer.clicked.connect(self._on_transfer)
        self._btn_scan.clicked.connect(self._on_process)

        # Navegación
        self._btn_first.clicked.connect(self._on_first)
        self._btn_prev.clicked.connect(self._on_prev)
        self._btn_next.clicked.connect(self._on_next)
        self._btn_last.clicked.connect(self._on_last)
        self._btn_next_barcode.clicked.connect(self._on_next_barcode)
        self._btn_next_review.clicked.connect(self._on_next_review)

        # Miniaturas
        self._thumbnail_panel.page_selected.connect(self._navigate_to)
        self._thumbnail_panel.page_double_clicked.connect(self._navigate_to)

        # Manipulación
        self._btn_mark.clicked.connect(self._on_mark_page)
        self._btn_rotate.clicked.connect(self._on_rotate_90)
        self._btn_delete_from.clicked.connect(self._on_delete_from_current)

        # Origen
        self._radio_scanner.toggled.connect(self._on_source_changed)

    def _setup_shortcuts(self) -> None:
        """Atajos de teclado."""
        # Ctrl+P: re-procesar página actual (UI-11)
        QShortcut(
            QKeySequence("Ctrl+P"), self,
        ).activated.connect(self._on_reprocess_page)

        # Ctrl+F: ajustar a página
        QShortcut(
            QKeySequence("Ctrl+F"), self,
        ).activated.connect(self._viewer.fit_to_page)

        # Ctrl++/-: zoom
        QShortcut(
            QKeySequence("Ctrl++"), self,
        ).activated.connect(self._viewer.zoom_in)
        QShortcut(
            QKeySequence("Ctrl+-"), self,
        ).activated.connect(self._viewer.zoom_out)

    def _configure_metadata(self) -> None:
        """Configura los campos de lote e indexación según la app."""
        if self._application is None:
            return
        try:
            batch_fields = json.loads(self._application.batch_fields_json)
        except (json.JSONDecodeError, TypeError):
            batch_fields = []
        try:
            index_fields = json.loads(self._application.index_fields_json)
        except (json.JSONDecodeError, TypeError):
            index_fields = []

        self._metadata_panel.configure(batch_fields, index_fields)

    # ==================================================================
    # Gestión de lote
    # ==================================================================

    def _create_batch(self) -> None:
        """Crea un lote nuevo para esta sesión de trabajo."""
        images_dir = APP_DATA_DIR / "images"
        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            batch = svc.create_batch(application_id=self._app_id)
            session.commit()
            self._batch_id = batch.id

        self._pages = []
        self._current_page_index = -1
        self._update_page_info()
        self._status_bar.showMessage(
            f"Lote {self._batch_id} creado", 3000,
        )

    def _reload_pages(self) -> None:
        """Recarga la lista de páginas desde BD."""
        if self._batch_id is None:
            return
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            self._pages = page_repo.get_by_batch(self._batch_id)
            # Expunge para desacoplar de la sesión
            for p in self._pages:
                session.expunge(p)

    # ==================================================================
    # Escaneo / Importación (UI-05, UI-10, UI-13)
    # ==================================================================

    def _on_process(self) -> None:
        """Inicia el proceso de adquisición + reconocimiento."""
        if self._scan_worker and self._scan_worker.isRunning():
            QMessageBox.information(
                self, "En proceso",
                "Ya hay un proceso de adquisición en curso.",
            )
            return

        if self._radio_scanner.isChecked():
            self._start_scanner()
        else:
            self._start_import()

    def _start_scanner(self) -> None:
        """Inicia adquisición desde escáner."""
        source = self._combo_source.currentText()
        if not source:
            QMessageBox.warning(
                self, "Sin fuente",
                "Selecciona un escáner primero.",
            )
            return

        from app.services.scanner_service import ScanConfig, create_scanner

        try:
            scanner = create_scanner(
                self._application.scanner_backend
                if self._application else None,
            )
        except RuntimeError as e:
            QMessageBox.critical(self, "Error de escáner", str(e))
            return

        self._scan_worker = ScanWorker(
            mode="scanner",
            source=source,
            scanner=scanner,
            scan_config=ScanConfig(),
        )
        self._start_workers()

    def _start_import(self) -> None:
        """Inicia importación desde fichero o carpeta."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar documento",
            str(Path.home()),
            "Documentos (*.pdf *.tiff *.tif *.jpg *.jpeg *.png *.bmp);;"
            "Todos (*)",
        )
        if not path:
            return

        suffix = Path(path).suffix.lower()
        mode = "import_pdf" if suffix == ".pdf" else "import_file"

        self._scan_worker = ScanWorker(
            mode=mode,
            source=path,
            import_service=self._import_service,
        )
        self._start_workers()

    def _start_workers(self) -> None:
        """Arranca ScanWorker y RecognitionWorker en paralelo."""
        # Preparar contextos ligeros
        app_ctx = AppContext(
            id=self._app_id,
            name=self._application.name if self._application else "",
            description=(
                self._application.description if self._application else ""
            ),
        )
        batch_ctx = BatchContext(
            id=self._batch_id or 0,
        )

        self._recognition_worker = RecognitionWorker(
            executor=self._executor,
            app_context=app_ctx,
            batch_context=batch_ctx,
        )

        # Conectar señales del scan worker
        self._scan_worker.page_acquired.connect(self._on_page_acquired)
        self._scan_worker.finished_scanning.connect(self._on_scan_finished)
        self._scan_worker.error_occurred.connect(self._on_scan_error)

        # Conectar señales del recognition worker
        self._recognition_worker.page_processed.connect(
            self._on_page_processed,
        )
        self._recognition_worker.all_processed.connect(
            self._on_all_processed,
        )
        self._recognition_worker.page_error.connect(self._on_page_error)
        self._recognition_worker.progress.connect(self._on_progress)

        # Mostrar progreso
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._btn_process.setEnabled(False)

        # Arrancar
        self._recognition_worker.start()
        self._scan_worker.start()
        self._status_bar.showMessage("Procesando...")

    def _on_page_acquired(self, page_index: int, image: np.ndarray) -> None:
        """Una página ha sido adquirida: guardar, thumbnail, encolar."""
        images_dir = APP_DATA_DIR / "images"
        output_format = (
            self._application.output_format if self._application else "tiff"
        )

        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            pages = svc.add_pages(
                self._batch_id, [image], output_format=output_format,
            )
            session.commit()
            for p in pages:
                session.expunge(p)
                self._pages.append(p)

        # Añadir thumbnail
        self._thumbnail_panel.add_thumbnail(page_index, image)

        # Encolar para reconocimiento
        if self._recognition_worker:
            self._recognition_worker.enqueue_page(page_index, image)

        # Si es la primera página, navegar a ella
        if self._current_page_index < 0:
            self._navigate_to(0)

        self._update_page_info()

    def _on_scan_finished(self, total: int) -> None:
        """El escaneo/importación ha terminado."""
        log.info("Adquisición completada: %d páginas", total)
        if self._recognition_worker:
            self._recognition_worker.signal_no_more_pages()

    def _on_scan_error(self, error: str) -> None:
        """Error durante la adquisición."""
        self._progress_bar.setVisible(False)
        self._btn_process.setEnabled(True)
        QMessageBox.critical(self, "Error de adquisición", error)

    def _on_page_processed(self, page_index: int, page_ctx: Any) -> None:
        """Una página ha sido procesada por el pipeline."""
        # Persistir resultados
        self._persist_page_results(page_index, page_ctx)

        # Actualizar thumbnail
        state = determine_page_state(
            needs_review=page_ctx.flags.needs_review,
            barcodes=page_ctx.barcodes,
            ai_fields_json=json.dumps(page_ctx.ai_fields)
            if page_ctx.ai_fields else "{}",
        )
        self._thumbnail_panel.update_thumbnail_state(page_index, state)

        # Si es la página actual, actualizar visor
        if page_index == self._current_page_index:
            self._viewer.set_state(state)
            self._viewer.set_overlays(barcodes=page_ctx.barcodes)
            self._barcode_panel.set_page_barcodes(page_ctx.barcodes)
            self._reload_pages()
            if 0 <= page_index < len(self._pages):
                page = self._pages[page_index]
                self._metadata_panel.set_verification_data(
                    ocr_text=page.ocr_text,
                    ai_fields_json=page.ai_fields_json,
                    errors_json=page.processing_errors_json,
                    script_errors_json=page.script_errors_json,
                )

    def _persist_page_results(self, page_index: int, page_ctx: Any) -> None:
        """Guarda los resultados del pipeline en BD."""
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            pages = page_repo.get_by_batch(self._batch_id)

            page = None
            for p in pages:
                if p.page_index == page_index:
                    page = p
                    break

            if page is None:
                log.warning("Página %d no encontrada en BD", page_index)
                return

            page.ocr_text = page_ctx.ocr_text or ""
            page.ai_fields_json = json.dumps(
                page_ctx.ai_fields, ensure_ascii=False,
            ) if page_ctx.ai_fields else "{}"
            page.needs_review = page_ctx.flags.needs_review
            page.review_reason = page_ctx.flags.review_reason
            page.processing_errors_json = json.dumps(
                page_ctx.flags.processing_errors, ensure_ascii=False,
            )
            page.script_errors_json = json.dumps(
                [e for e in page_ctx.flags.script_errors],
                ensure_ascii=False,
            )

            # Persistir barcodes
            for bc in page_ctx.barcodes:
                from app.models.barcode import Barcode as BarcodeModel
                barcode = BarcodeModel(
                    page_id=page.id,
                    value=bc.value,
                    symbology=bc.symbology,
                    engine=bc.engine,
                    step_id=bc.step_id,
                    quality=bc.quality,
                    pos_x=bc.pos_x,
                    pos_y=bc.pos_y,
                    pos_w=bc.pos_w,
                    pos_h=bc.pos_h,
                    role=bc.role,
                )
                session.add(barcode)

            session.commit()

    def _on_page_error(self, page_index: int, error: str) -> None:
        """Error procesando una página."""
        log.error("Error en página %d: %s", page_index, error)
        self._thumbnail_panel.update_thumbnail_state(
            page_index, PageState.NEEDS_REVIEW,
        )

    def _on_all_processed(self) -> None:
        """Todo el pipeline ha terminado."""
        self._progress_bar.setVisible(False)
        self._btn_process.setEnabled(True)
        self._reload_pages()
        self._update_lot_counters()

        # Transicionar estado del lote
        if self._batch_id:
            with self._session_factory() as session:
                svc = BatchService(session, APP_DATA_DIR / "images")
                svc.transition_state(self._batch_id, "read")
                session.commit()

        self._fire_event("on_scan_complete")
        self._status_bar.showMessage("Procesamiento completado", 5000)

        # Auto-transferencia (APP-02)
        if self._application and self._application.auto_transfer:
            self._on_transfer()

    def _on_progress(self, completed: int, total: int) -> None:
        """Actualiza la barra de progreso."""
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(completed)

    # ==================================================================
    # Navegación (UI-09)
    # ==================================================================

    def _navigate_to(self, page_index: int) -> None:
        """Navega a una página por su índice en la lista."""
        if not self._pages or page_index < 0 or page_index >= len(self._pages):
            return

        self._current_page_index = page_index
        page = self._pages[page_index]

        # Cargar imagen
        image = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            log.error("No se pudo cargar imagen: %s", page.image_path)
            return

        # Determinar estado
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            db_page = page_repo.get_by_id(page.id)
            barcodes = db_page.barcodes if db_page else []
            state = determine_page_state(
                needs_review=page.needs_review,
                barcodes=barcodes,
                ai_fields_json=page.ai_fields_json,
            )

            # Actualizar visor
            self._viewer.set_image(image, state)
            self._viewer.set_overlays(barcodes=barcodes)

            # Actualizar panel de barcodes
            self._barcode_panel.set_page_barcodes(barcodes)

        # Actualizar metadatos
        try:
            idx_fields = json.loads(page.index_fields_json)
        except (json.JSONDecodeError, TypeError):
            idx_fields = {}
        self._metadata_panel.set_index_fields(idx_fields)
        self._metadata_panel.set_verification_data(
            ocr_text=page.ocr_text,
            ai_fields_json=page.ai_fields_json,
            errors_json=page.processing_errors_json,
            script_errors_json=page.script_errors_json,
        )

        # Actualizar thumbnail y página info
        self._thumbnail_panel.set_current(page_index)
        self._update_page_info()

    def _on_first(self) -> None:
        self._navigate_to(0)

    def _on_prev(self) -> None:
        if self._current_page_index > 0:
            self._navigate_to(self._current_page_index - 1)

    def _on_next(self) -> None:
        if self._current_page_index < len(self._pages) - 1:
            self._navigate_to(self._current_page_index + 1)

    def _on_last(self) -> None:
        if self._pages:
            self._navigate_to(len(self._pages) - 1)

    def _on_next_barcode(self) -> None:
        """Navega a la siguiente página con barcodes."""
        for i in range(self._current_page_index + 1, len(self._pages)):
            page = self._pages[i]
            with self._session_factory() as session:
                page_repo = PageRepository(session)
                db_page = page_repo.get_by_id(page.id)
                if db_page and db_page.barcodes:
                    self._navigate_to(i)
                    return
        self._status_bar.showMessage("No hay más páginas con barcode", 2000)

    def _on_next_review(self) -> None:
        """Navega a la siguiente página con needs_review."""
        for i in range(self._current_page_index + 1, len(self._pages)):
            if self._pages[i].needs_review:
                self._navigate_to(i)
                return
        self._status_bar.showMessage("No hay más páginas pendientes", 2000)

    def _update_page_info(self) -> None:
        """Actualiza el indicador de página."""
        total = len(self._pages)
        current = self._current_page_index + 1 if total > 0 else 0
        self._lbl_page_info.setText(f" {current} / {total} ")

    # ==================================================================
    # Transferencia (UI-06)
    # ==================================================================

    def _on_transfer(self) -> None:
        """Ejecuta el flujo de transferencia."""
        if self._batch_id is None or not self._pages:
            QMessageBox.information(
                self, "Sin datos", "No hay páginas para transferir.",
            )
            return

        if self._transfer_worker and self._transfer_worker.isRunning():
            return

        # 1. Validación (on_transfer_validate)
        result = self._fire_event("on_transfer_validate")
        if result is False:
            QMessageBox.warning(
                self, "Transferencia cancelada",
                "La validación pre-transferencia ha fallado.",
            )
            return

        # 2. Confirmación
        reply = QMessageBox.question(
            self, "Confirmar transferencia",
            f"¿Transferir lote con {len(self._pages)} página(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 3. Preparar datos
        config = parse_transfer_config(
            self._application.transfer_json if self._application else "{}",
        )
        batch_fields = {}
        if self._batch_id:
            with self._session_factory() as session:
                svc = BatchService(session, APP_DATA_DIR / "images")
                batch_fields = svc.get_fields(self._batch_id)

        pages_data = []
        for page in self._pages:
            if page.is_excluded:
                continue
            try:
                idx_fields = json.loads(page.index_fields_json)
            except (json.JSONDecodeError, TypeError):
                idx_fields = {}
            pages_data.append({
                "image_path": page.image_path,
                "page_index": page.page_index,
                "index_fields": idx_fields,
                "ocr_text": page.ocr_text,
                "ai_fields": page.ai_fields_json,
            })

        # 4. Lanzar worker
        self._transfer_worker = TransferWorker(
            transfer_service=self._transfer_service,
            config=config,
            pages=pages_data,
            batch_fields=batch_fields,
            batch_id=self._batch_id,
        )
        self._transfer_worker.transfer_finished.connect(
            self._on_transfer_finished,
        )
        self._transfer_worker.transfer_error.connect(
            self._on_transfer_error,
        )
        self._btn_transfer.setEnabled(False)
        self._transfer_worker.start()

    def _on_transfer_finished(self, result: Any) -> None:
        """Transferencia completada."""
        self._btn_transfer.setEnabled(True)

        if result.success:
            # Transicionar estado
            if self._batch_id:
                with self._session_factory() as session:
                    svc = BatchService(session, APP_DATA_DIR / "images")
                    svc.transition_state(self._batch_id, "exported")
                    session.commit()

            QMessageBox.information(
                self, "Transferencia completada",
                f"Se transfirieron {result.files_transferred} fichero(s)\n"
                f"Destino: {result.output_path}",
            )

            # Cerrar después de transferencia (APP-03)
            if self._application and self._application.close_after_transfer:
                self.close()
        else:
            errors = "\n".join(result.errors[:5])
            QMessageBox.warning(
                self, "Transferencia con errores",
                f"Ficheros: {result.files_transferred}\nErrores:\n{errors}",
            )

    def _on_transfer_error(self, error: str) -> None:
        """Error durante la transferencia."""
        self._btn_transfer.setEnabled(True)
        QMessageBox.critical(self, "Error de transferencia", error)

    # ==================================================================
    # Manipulación de páginas (UI-07)
    # ==================================================================

    def _on_mark_page(self) -> None:
        """Marca/desmarca la página actual como excluida."""
        if self._current_page_index < 0:
            return
        page = self._pages[self._current_page_index]

        with self._session_factory() as session:
            page_repo = PageRepository(session)
            db_page = page_repo.get_by_id(page.id)
            if db_page:
                db_page.is_excluded = not db_page.is_excluded
                session.commit()
                page.is_excluded = db_page.is_excluded

        status = "excluida" if page.is_excluded else "incluida"
        self._status_bar.showMessage(f"Página {status}", 2000)

    def _on_rotate_90(self) -> None:
        """Rota la página actual 90° en sentido horario."""
        if self._current_page_index < 0:
            return
        page = self._pages[self._current_page_index]

        image = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            return

        rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        cv2.imwrite(page.image_path, rotated)

        # Refrescar visor
        self._navigate_to(self._current_page_index)

    def _on_delete_from_current(self) -> None:
        """Elimina páginas desde la actual hasta el final."""
        if self._current_page_index < 0:
            return

        count = len(self._pages) - self._current_page_index
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar {count} página(s) desde la actual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pages_to_delete = self._pages[self._current_page_index:]
        images_dir = APP_DATA_DIR / "images"

        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            for page in pages_to_delete:
                svc.remove_page(page.id)
            session.commit()

        # Recargar
        self._reload_pages()
        self._thumbnail_panel.clear()
        for i, page in enumerate(self._pages):
            img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                state = determine_page_state(
                    needs_review=page.needs_review,
                    ai_fields_json=page.ai_fields_json,
                )
                self._thumbnail_panel.add_thumbnail(i, img, state)

        if self._pages:
            idx = min(self._current_page_index, len(self._pages) - 1)
            self._navigate_to(idx)
        else:
            self._current_page_index = -1
            self._viewer.clear()
        self._update_page_info()

    # ==================================================================
    # Re-procesamiento (UI-11)
    # ==================================================================

    def _on_reprocess_page(self) -> None:
        """Re-ejecuta el pipeline en la página actual (Ctrl+P)."""
        if self._current_page_index < 0 or self._executor is None:
            return

        page = self._pages[self._current_page_index]
        image = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            return

        app_ctx = AppContext(
            id=self._app_id,
            name=self._application.name if self._application else "",
        )
        batch_ctx = BatchContext(id=self._batch_id or 0)

        # Re-usar el recognition worker para una sola página
        self._recognition_worker = RecognitionWorker(
            executor=self._executor,
            app_context=app_ctx,
            batch_context=batch_ctx,
        )
        self._recognition_worker.page_processed.connect(
            self._on_page_processed,
        )
        self._recognition_worker.all_processed.connect(
            lambda: self._status_bar.showMessage("Re-procesado completado", 3000),
        )
        self._recognition_worker.start()
        self._recognition_worker.enqueue_page(
            self._current_page_index, image,
        )
        self._recognition_worker.signal_no_more_pages()
        self._status_bar.showMessage("Re-procesando página...")

    # ==================================================================
    # Eventos de ciclo de vida
    # ==================================================================

    def _fire_event(self, event_name: str) -> Any:
        """Ejecuta un entry point de ciclo de vida."""
        app_ctx = AppContext(
            id=self._app_id,
            name=self._application.name if self._application else "",
        )
        batch_ctx = BatchContext(id=self._batch_id or 0)

        return self._script_engine.run_event(
            script_id=event_name,
            entry_point=event_name,
            app=app_ctx,
            batch=batch_ctx,
        )

    # ==================================================================
    # Contadores y origen
    # ==================================================================

    def _update_lot_counters(self) -> None:
        """Actualiza los contadores del panel de barcodes."""
        if self._batch_id is None:
            return
        with self._session_factory() as session:
            svc = BatchService(session, APP_DATA_DIR / "images")
            stats = svc.get_stats(self._batch_id)

        # Contar barcodes
        total_barcodes = 0
        separators = 0
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            pages = page_repo.get_by_batch(self._batch_id)
            pages_with_bc = 0
            for p in pages:
                if p.barcodes:
                    pages_with_bc += 1
                    total_barcodes += len(p.barcodes)
                    separators += sum(
                        1 for b in p.barcodes if b.role == "separator"
                    )

        self._barcode_panel.set_lot_counters({
            "total_pages": stats.get("total_pages", 0),
            "with_barcode": pages_with_bc,
            "separators": separators,
            "needs_review": stats.get("needs_review", 0),
        })

    def _on_source_changed(self, scanner_checked: bool) -> None:
        """Actualiza el combo de origen según escáner o importar."""
        self._combo_source.clear()
        if scanner_checked:
            try:
                from app.services.scanner_service import create_scanner
                scanner = create_scanner(
                    self._application.scanner_backend
                    if self._application else None,
                )
                sources = scanner.list_sources()
                self._combo_source.addItems(sources)
            except Exception as e:
                log.warning("No se pudieron listar escáneres: %s", e)
        else:
            self._combo_source.setPlaceholderText(
                "Usa el botón para seleccionar archivo...",
            )

    # ==================================================================
    # Teclado (UI-12)
    # ==================================================================

    def keyPressEvent(self, event) -> None:
        """Despacha on_key_event si hay combinación Ctrl/Alt/Shift."""
        mods = event.modifiers()
        has_mod = bool(
            mods & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        )
        if has_mod and event.text():
            key_str = event.keyCombination().key().name.decode()
            self._script_engine.run_event(
                script_id="on_key_event",
                entry_point="on_key_event",
                app=AppContext(id=self._app_id),
                batch=BatchContext(id=self._batch_id or 0),
                key=key_str,
            )
        super().keyPressEvent(event)

    # ==================================================================
    # Cierre
    # ==================================================================

    def closeEvent(self, event) -> None:
        """Detiene workers y ejecuta on_app_end."""
        # Detener workers
        for worker in (
            self._scan_worker,
            self._recognition_worker,
            self._transfer_worker,
        ):
            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.wait(3000)

        self._fire_event("on_app_end")
        self.closed.emit()
        super().closeEvent(event)
