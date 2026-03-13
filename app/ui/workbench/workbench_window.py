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
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
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
from app.services.barcode_service import BarcodeService
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
from app.ui.workbench.viewer_overlay import ViewerOverlay
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    RecognitionWorker,
)
from app.services.scanner_service import ScanConfig
from app.ui.workbench.scanner_config_dialog import ScannerConfigDialog
from app.workers.scan_worker import ScanWorker
from app.workers.transfer_worker import TransferWorker
from config.settings import APP_DATA_DIR, APP_IMAGES_DIR

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
        *,
        batch_id: int | None = None,
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
        self._barcode_service = BarcodeService()
        self._import_service = ImportService()
        self._transfer_service = TransferService()
        self._scanner: Any = None  # Instancia reutilizable de BaseScanner
        self._last_scan_options: dict[str, Any] = {}  # Opciones del último escaneo
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

        if batch_id is not None:
            self._load_existing_batch(batch_id)
        else:
            self._restore_or_create_batch()
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

        # Crear executor con todos los servicios disponibles
        self._executor = PipelineExecutor(
            steps=steps,
            image_service=self._image_service,
            script_engine=self._script_engine,
            barcode_service=self._barcode_service,
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
        self.setWindowTitle(f"DocScan Studio \u2014 {app_name}")
        self.setMinimumSize(1280, 800)
        self.setAcceptDrops(True)

        # Color de fondo personalizado (APP-04)
        if self._application and self._application.background_color:
            self.setStyleSheet(
                f"QMainWindow {{ background-color: "
                f"{self._application.background_color}; }}"
            )

        # --- Toolbar: Adquisición + Transferencia ---
        self._create_toolbar()

        # --- Layout principal con splitter ---
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: miniaturas
        self._thumbnail_panel = ThumbnailPanel()

        # Panel central: visor con overlay
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._viewer = DocumentViewer()
        center_layout.addWidget(self._viewer, stretch=1)

        # Overlay flotante sobre el visor
        self._viewer_overlay = ViewerOverlay(self._viewer)
        self._viewer_overlay.setVisible(True)

        # Panel derecho: barcodes + metadatos
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._barcode_panel = BarcodePanel()
        self._metadata_panel = MetadataPanel()

        right_layout.addWidget(self._barcode_panel, stretch=1)
        right_layout.addWidget(self._metadata_panel, stretch=2)

        # Armar splitter
        self._splitter.addWidget(self._thumbnail_panel)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 0)   # miniaturas: ancho fijo
        self._splitter.setStretchFactor(1, 7)   # visor: máximo
        self._splitter.setStretchFactor(2, 2)   # derecha: menor
        # Tamaños iniciales en píxeles: miniaturas 170, visor 750, derecha 300
        self._splitter.setSizes([170, 750, 300])

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

        # Iconos del overlay según tema actual
        self._update_overlay_icons()

        # Pestaña por defecto (APP-07)
        if self._application:
            self._metadata_panel.set_default_tab(
                self._application.default_tab or "lote",
            )

    def _create_toolbar(self) -> None:
        """Crea la barra de herramientas: adquisición y transferencia."""
        toolbar = QToolBar("Workbench")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Origen: Escáner / Importar
        self._radio_scanner = QRadioButton("Esc\u00e1ner")
        self._radio_import = QRadioButton("Importar")
        self._radio_import.setChecked(True)

        self._combo_source = QComboBox()
        self._combo_source.setMinimumWidth(180)
        self._combo_source.setEditable(False)
        self._combo_source.setPlaceholderText("Seleccionar origen...")

        self._combo_source_type = QComboBox()
        self._combo_source_type.addItem("Flatbed", "flatbed")
        self._combo_source_type.addItem("ADF", "adf")
        self._combo_source_type.setFixedWidth(90)

        toolbar.addWidget(self._radio_scanner)
        toolbar.addWidget(self._radio_import)
        toolbar.addWidget(self._combo_source)
        toolbar.addWidget(self._combo_source_type)

        self._chk_scanner_config = QCheckBox("Configurar")
        self._chk_scanner_config.setToolTip(
            "Mostrar opciones del escáner antes de digitalizar"
        )
        self._chk_scanner_config.setChecked(False)
        toolbar.addWidget(self._chk_scanner_config)
        toolbar.addSeparator()

        # Botón principal de acción
        self._btn_process = QPushButton("Escanear / Importar")
        self._btn_process.setProperty("cssClass", "primary")
        toolbar.addWidget(self._btn_process)

        toolbar.addSeparator()

        # Transferir
        self._btn_transfer = QPushButton("Transferir")
        toolbar.addWidget(self._btn_transfer)

        toolbar.addSeparator()

        # Cerrar lote (sin transferir)
        self._btn_close_batch = QPushButton("Cerrar lote")
        toolbar.addWidget(self._btn_close_batch)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        # Toggle tema
        from app.ui.theme_manager import ThemeManager
        self._theme_manager = ThemeManager()
        self._btn_theme = QPushButton()
        self._btn_theme.setToolTip("Cambiar tema claro/oscuro")
        self._update_theme_button()
        toolbar.addWidget(self._btn_theme)

        from app.ui.icon_factory import icon_font_decrease, icon_font_increase
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

    def _update_theme_button(self) -> None:
        from app.ui.icon_factory import icon_moon, icon_sun
        if self._theme_manager.is_dark:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_sun())
        else:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_moon("#5c5f77"))

    def _connect_signals(self) -> None:
        """Conecta todas las señales de la UI."""
        # Procesar / Transferir / Cerrar lote
        self._btn_process.clicked.connect(self._on_process)
        self._btn_transfer.clicked.connect(self._on_transfer)
        self._btn_close_batch.clicked.connect(self._on_close_batch)

        # Origen
        self._radio_scanner.toggled.connect(self._on_source_changed)

        # Visor resize → reposicionar overlay
        self._viewer.viewer_resized.connect(self._reposition_overlay)

        # Tema y fuente
        self._btn_theme.clicked.connect(self._on_toggle_theme)
        self._btn_font_up.clicked.connect(self._theme_manager.increase_font)
        self._btn_font_down.clicked.connect(self._theme_manager.decrease_font)
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

        # Overlay: navegación
        self._viewer_overlay.nav_first.connect(self._on_first)
        self._viewer_overlay.nav_prev.connect(self._on_prev)
        self._viewer_overlay.nav_next.connect(self._on_next)
        self._viewer_overlay.nav_last.connect(self._on_last)
        self._viewer_overlay.nav_script.connect(self._on_nav_script)

        # Overlay: zoom
        self._viewer_overlay.zoom_in_requested.connect(self._viewer.zoom_in)
        self._viewer_overlay.zoom_out_requested.connect(self._viewer.zoom_out)
        self._viewer_overlay.zoom_fit_requested.connect(
            self._viewer.fit_to_page,
        )
        self._viewer_overlay.zoom_100_requested.connect(self._on_zoom_100)

        # Overlay: herramientas
        self._viewer_overlay.rotate_requested.connect(self._on_rotate_90)
        self._viewer_overlay.mark_requested.connect(self._on_mark_page)
        self._viewer_overlay.delete_current_requested.connect(
            self._on_delete_current_page,
        )
        self._viewer_overlay.delete_from_requested.connect(
            self._on_delete_from_current,
        )

        # Campos de lote
        self._metadata_panel.batch_field_changed.connect(self._on_batch_field_changed)

        # Miniaturas
        self._thumbnail_panel.page_selected.connect(self._navigate_to)
        self._thumbnail_panel.page_double_clicked.connect(self._navigate_to)

        # Barcode panel buttons
        self._barcode_panel.insert_barcode_requested.connect(
            self._on_insert_barcode,
        )
        self._barcode_panel.delete_barcode_requested.connect(
            self._on_delete_barcode,
        )

    def _setup_shortcuts(self) -> None:
        """Atajos de teclado."""
        QShortcut(
            QKeySequence("Ctrl+P"), self,
        ).activated.connect(self._on_reprocess_page)
        QShortcut(
            QKeySequence("Ctrl+F"), self,
        ).activated.connect(self._viewer.fit_to_page)
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
            raw_batch = json.loads(self._application.batch_fields_json)
        except (json.JSONDecodeError, TypeError):
            raw_batch = []
        try:
            index_fields = json.loads(self._application.index_fields_json)
        except (json.JSONDecodeError, TypeError):
            index_fields = []

        # Mapear formato tab_batch_fields → MetadataPanel.configure()
        type_map = {
            "texto": "Texto", "fecha": "Fecha",
            "lista": "Lista", "numérico": "Número",
        }
        batch_fields = []
        for f in raw_batch:
            cfg = f.get("config", {})
            entry: dict[str, Any] = {
                "name": f.get("label", ""),
                "type": type_map.get(f.get("type", "texto"), "Texto"),
                "required": f.get("required", False),
            }
            if f.get("type") == "lista":
                entry["choices"] = cfg.get("values", [])
            elif f.get("type") == "numérico":
                entry["min"] = cfg.get("min", 0)
                entry["max"] = cfg.get("max", 100)
                entry["step"] = cfg.get("step", 1)
            elif f.get("type") == "fecha":
                entry["date_format"] = cfg.get("format", "dd/MM/yyyy")
            batch_fields.append(entry)

        self._metadata_panel.configure(batch_fields, index_fields)

    def _on_batch_field_changed(self, field_name: str, value: str) -> None:
        """Persiste un campo de lote editado en BD."""
        if not self._batch_id:
            return
        try:
            from app.db.repositories.batch_repo import BatchRepository
            with self._session_factory() as session:
                repo = BatchRepository(session)
                batch = repo.get_by_id(self._batch_id)
                if batch is None:
                    return
                fields = json.loads(batch.fields_json or "{}")
                fields[field_name] = value
                batch.fields_json = json.dumps(fields, ensure_ascii=False)
                session.commit()
        except Exception as e:
            log.error("Error guardando campo de lote '%s': %s", field_name, e)

    # ==================================================================
    # Tema
    # ==================================================================

    def _on_toggle_theme(self) -> None:
        self._theme_manager.toggle_theme()

    def _on_theme_changed(self, _theme_name: str) -> None:
        self._update_theme_button()
        self._update_font_icons()
        self._update_overlay_icons()

    def _update_font_icons(self) -> None:
        from app.ui.icon_factory import icon_font_decrease, icon_font_increase
        color = "#cdd6f4" if self._theme_manager.is_dark else "#4c4f69"
        self._btn_font_up.setIcon(icon_font_increase(color, 32))
        self._btn_font_down.setIcon(icon_font_decrease(color, 32))

    def _update_overlay_icons(self) -> None:
        color = "#cdd6f4" if self._theme_manager.is_dark else "#4c4f69"
        self._viewer_overlay.update_icon_color(color)

    # ==================================================================
    # Gestión de lote
    # ==================================================================

    def _restore_or_create_batch(self) -> None:
        """Busca un lote abierto (no transferido) o crea uno nuevo."""
        from app.db.repositories.batch_repo import BatchRepository

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            batches = batch_repo.get_by_application(self._app_id)
            # Buscar el lote más reciente que no esté transferido ni con error
            for b in batches:
                if b.state in ("created", "read", "verified", "ready_to_export"):
                    self._load_existing_batch(b.id)
                    return

        # No hay lote abierto: crear uno nuevo
        self._create_new_batch()

    def _create_new_batch(self) -> None:
        """Crea un lote nuevo para esta sesión de trabajo."""
        images_dir = APP_IMAGES_DIR
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

    def _load_existing_batch(self, batch_id: int) -> None:
        """Carga un lote existente con sus páginas y miniaturas."""
        from app.db.repositories.batch_repo import BatchRepository

        with self._session_factory() as session:
            batch_repo = BatchRepository(session)
            batch = batch_repo.get_by_id(batch_id)
            if batch is None:
                self._create_new_batch()
                return
            self._batch_id = batch.id
            batch_fields = json.loads(batch.fields_json or "{}")

        self._metadata_panel.set_batch_fields(batch_fields)

        self._reload_pages()
        self._thumbnail_panel.clear()
        for i, page in enumerate(self._pages):
            img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                state = determine_page_state(
                    needs_review=page.needs_review,
                    ai_fields_json=page.ai_fields_json,
                    is_excluded=page.is_excluded,
                )
                self._thumbnail_panel.add_thumbnail(i, img, state)

        if self._pages:
            self._navigate_to(0)
        else:
            self._current_page_index = -1

        self._update_page_info()
        self._update_lot_counters()
        self._status_bar.showMessage(
            f"Lote {self._batch_id} cargado ({len(self._pages)} páginas)", 3000,
        )

    def _reload_pages(self) -> None:
        """Recarga la lista de páginas desde BD."""
        if self._batch_id is None:
            return
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            self._pages = page_repo.get_by_batch(self._batch_id)
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

    def _get_scanner(self) -> Any:
        """Devuelve la instancia reutilizable de escáner."""
        if self._scanner is None:
            from app.services.scanner_service import create_scanner
            self._scanner = create_scanner(
                self._application.scanner_backend
                if self._application else None,
            )
        return self._scanner

    def _start_scanner(self) -> None:
        """Inicia adquisición desde escáner."""
        source = self._combo_source.currentText()
        if not source:
            QMessageBox.warning(
                self, "Sin fuente",
                "Selecciona un escáner primero.",
            )
            return

        try:
            scanner = self._get_scanner()
        except RuntimeError as e:
            QMessageBox.critical(self, "Error de escáner", str(e))
            return

        source_type = self._combo_source_type.currentData() or "flatbed"
        scan_config = ScanConfig(source_type=source_type)

        if self._chk_scanner_config.isChecked():
            if scanner.supports_native_ui:
                # TWAIN/WIA: activar diálogo nativo del driver
                scan_config.show_ui = True
            else:
                # SANE: consultar opciones del dispositivo y mostrar diálogo
                try:
                    options = scanner.get_device_options(source)
                except Exception as e:
                    log.warning("Error consultando opciones: %s", e)
                    options = []

                if options:
                    # Aplicar valores de la sesión anterior
                    if self._last_scan_options:
                        for opt in options:
                            if opt.name in self._last_scan_options:
                                opt.value = self._last_scan_options[opt.name]

                    dialog = ScannerConfigDialog(options, self)
                    if dialog.exec() != ScannerConfigDialog.DialogCode.Accepted:
                        return
                    scan_config.extra_options = dialog.get_selected_options()
                    self._last_scan_options = dict(scan_config.extra_options)
                    # Sincronizar source_type si el usuario cambió 'source'
                    src_val = scan_config.extra_options.get("source", "")
                    if "adf" in str(src_val).lower():
                        scan_config.source_type = "adf"

        self._scan_worker = ScanWorker(
            mode="scanner",
            source=source,
            scanner=scanner,
            scan_config=scan_config,
        )
        self._start_workers()

    def _start_import(self) -> None:
        """Inicia importación desde uno o más ficheros."""
        # Si on_import está definido, delegar al script
        result = self._fire_event("on_import")
        if result is not None:
            return

        # Recuperar última ruta usada
        settings = QSettings("DocScanStudio", "Workbench")
        last_dir = settings.value(
            f"last_import_dir/{self._app_id}", str(Path.home()),
        )

        paths, _ = QFileDialog.getOpenFileNames(
            self, "Importar documentos",
            last_dir,
            "Documentos (*.pdf *.tiff *.tif *.jpg *.jpeg *.png *.bmp);;"
            "Todos (*)",
        )
        if not paths:
            return

        # Persistir la ruta del directorio
        settings.setValue(
            f"last_import_dir/{self._app_id}",
            str(Path(paths[0]).parent),
        )

        self._import_paths(paths)

    def _import_paths(self, paths: list[str]) -> None:
        """Importa una lista de rutas de fichero (común para diálogo y drag&drop)."""
        if not paths:
            return

        if len(paths) == 1:
            suffix = Path(paths[0]).suffix.lower()
            mode = "import_pdf" if suffix == ".pdf" else "import_file"
            self._scan_worker = ScanWorker(
                mode=mode,
                source=paths[0],
                import_service=self._import_service,
            )
        else:
            self._scan_worker = ScanWorker(
                mode="import_files",
                source=paths,
                import_service=self._import_service,
            )
        self._start_workers()

    def _start_workers(self) -> None:
        """Arranca ScanWorker y RecognitionWorker en paralelo."""
        app_ctx = self._build_app_context()
        batch_ctx = self._build_batch_context()

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
        images_dir = APP_IMAGES_DIR
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
                session.refresh(p)
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
        self._persist_page_results(page_index, page_ctx)

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

        if self._batch_id:
            with self._session_factory() as session:
                svc = BatchService(session, APP_IMAGES_DIR)
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
        cached_page = self._pages[page_index]

        with self._session_factory() as session:
            page_repo = PageRepository(session)
            page = page_repo.get_by_id(cached_page.id)
            if page is None:
                log.error("Página id=%d no encontrada en BD", cached_page.id)
                return

            # Leer barcodes dentro de la sesión (lazy-loaded)
            barcodes = list(page.barcodes)

            image = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                log.error("No se pudo cargar imagen: %s", page.image_path)
                return

            state = determine_page_state(
                needs_review=page.needs_review,
                barcodes=barcodes,
                ai_fields_json=page.ai_fields_json,
                is_excluded=page.is_excluded,
            )

            self._viewer.set_image(image, state)
            self._viewer.set_overlays(barcodes=barcodes)
            self._barcode_panel.set_page_barcodes(barcodes)

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

        self._thumbnail_panel.set_current(page_index)
        self._update_page_info()

    def _on_zoom_100(self) -> None:
        self._viewer.zoom_reset()

    def _on_first(self) -> None:
        self._navigate_to(0)

    def _on_prev(self) -> None:
        result = self._fire_event(
            "on_navigate_prev",
            current_page_index=self._current_page_index,
            total_pages=len(self._pages),
        )
        if isinstance(result, int) and 0 <= result < len(self._pages):
            self._navigate_to(result)
        elif self._current_page_index > 0:
            self._navigate_to(self._current_page_index - 1)

    def _on_next(self) -> None:
        result = self._fire_event(
            "on_navigate_next",
            current_page_index=self._current_page_index,
            total_pages=len(self._pages),
        )
        if isinstance(result, int) and 0 <= result < len(self._pages):
            self._navigate_to(result)
        elif self._current_page_index < len(self._pages) - 1:
            self._navigate_to(self._current_page_index + 1)

    def _on_last(self) -> None:
        if self._pages:
            self._navigate_to(len(self._pages) - 1)

    def _on_nav_script(self) -> None:
        """Ejecuta el evento on_navigate_script para navegación programable."""
        # Construir resumen de páginas para el script
        pages_info = []
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            for cached in self._pages:
                db_page = page_repo.get_by_id(cached.id)
                barcodes = []
                if db_page and db_page.barcodes:
                    barcodes = [
                        {"value": b.value, "symbology": b.symbology, "role": b.role or ""}
                        for b in db_page.barcodes
                    ]
                pages_info.append({
                    "page_index": cached.page_index,
                    "barcodes": barcodes,
                    "needs_review": db_page.needs_review if db_page else False,
                })

        result = self._fire_event(
            "on_navigate_script",
            current_page_index=self._current_page_index,
            total_pages=len(self._pages),
            pages=pages_info,
        )
        if isinstance(result, int) and 0 <= result < len(self._pages):
            self._navigate_to(result)
        else:
            self._status_bar.showMessage(
                "Script de navegación: sin destino", 2000,
            )

    def _update_page_info(self) -> None:
        """Actualiza el indicador de página en el overlay."""
        total = len(self._pages)
        current = self._current_page_index + 1 if total > 0 else 0
        self._viewer_overlay.update_page_info(current, total)

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
        # Leer campos actuales del panel (incluye valores por defecto no tocados)
        batch_fields = self._metadata_panel.get_batch_fields()
        # Persistir en BD por si no se habían guardado aún
        if self._batch_id:
            with self._session_factory() as session:
                from app.db.repositories.batch_repo import BatchRepository
                repo = BatchRepository(session)
                batch = repo.get_by_id(self._batch_id)
                if batch:
                    batch.fields_json = json.dumps(batch_fields, ensure_ascii=False)
                    session.commit()

        pages_data = []
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            for page in self._pages:
                if page.is_excluded:
                    continue
                try:
                    idx_fields = json.loads(page.index_fields_json)
                except (json.JSONDecodeError, TypeError):
                    idx_fields = {}
                # Obtener primer barcode para el patrón de nombre
                db_page = page_repo.get_by_id(page.id)
                barcodes = list(db_page.barcodes) if db_page else []
                first_bc = barcodes[0].value if barcodes else ""
                pages_data.append({
                    "image_path": page.image_path,
                    "page_index": page.page_index,
                    "index_fields": idx_fields,
                    "ocr_text": page.ocr_text,
                    "ai_fields": page.ai_fields_json,
                    "first_barcode": first_bc,
                })

        # 4. Lanzar worker (modo avanzado o estándar)
        if self._script_engine.is_compiled("on_transfer_advanced"):
            self._transfer_worker = TransferWorker(
                transfer_service=self._transfer_service,
                config=config,
                pages=pages_data,
                batch_fields=batch_fields,
                batch_id=self._batch_id,
                script_engine=self._script_engine,
                advanced_contexts={
                    "app": self._build_app_context(),
                    "batch": self._build_batch_context(),
                },
            )
        else:
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
        self._transfer_worker.page_transferred.connect(
            self._on_page_transferred,
        )
        self._btn_transfer.setEnabled(False)
        self._transfer_worker.start()

    def _on_page_transferred(self, page_index: int, success: bool) -> None:
        """Notifica por cada página transferida (on_transfer_page)."""
        self._fire_event(
            "on_transfer_page",
            page_index=page_index,
            success=success,
        )

    def _on_transfer_finished(self, result: Any) -> None:
        """Transferencia completada."""
        self._btn_transfer.setEnabled(True)

        if result.success:
            if self._batch_id:
                with self._session_factory() as session:
                    svc = BatchService(session, APP_IMAGES_DIR)
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
                self._start_new_batch_after_export()
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
    # Cerrar lote sin transferir
    # ==================================================================

    def _start_new_batch_after_export(self) -> None:
        """Cierra el lote exportado y prepara uno nuevo conservando campos de lote."""
        saved_fields = self._metadata_panel.get_batch_fields()

        self._thumbnail_panel.clear()
        self._viewer.clear()
        self._barcode_panel.clear()

        self._create_new_batch()
        self._metadata_panel.set_batch_fields(saved_fields)

        # Persistir los campos en el nuevo lote
        if self._batch_id:
            with self._session_factory() as session:
                from app.db.repositories.batch_repo import BatchRepository
                repo = BatchRepository(session)
                batch = repo.get_by_id(self._batch_id)
                if batch:
                    batch.fields_json = json.dumps(saved_fields, ensure_ascii=False)
                    session.commit()

        self._status_bar.showMessage("Nuevo lote creado", 3000)

    def _on_close_batch(self) -> None:
        """Cierra el lote actual y crea uno nuevo."""
        if self._batch_id is None or not self._pages:
            QMessageBox.information(
                self, "Sin lote", "No hay un lote activo con páginas.",
            )
            return

        if self._recognition_worker and self._recognition_worker.isRunning():
            QMessageBox.warning(
                self, "Procesando",
                "Espera a que termine el reconocimiento antes de cerrar el lote.",
            )
            return

        reply = QMessageBox.question(
            self, "Cerrar lote",
            f"¿Cerrar el lote {self._batch_id} sin transferir?\n"
            "Se podrá reabrir desde el gestor de lotes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Transicionar a "verified" para indicar que está cerrado pero no transferido
        with self._session_factory() as session:
            svc = BatchService(session, APP_IMAGES_DIR)
            svc.transition_state(self._batch_id, "verified")
            session.commit()

        self._status_bar.showMessage(
            f"Lote {self._batch_id} cerrado", 3000,
        )
        self.close()

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

        # Actualizar borde en thumbnail y visor
        state = self._determine_current_state(page)
        self._thumbnail_panel.update_thumbnail_state(
            self._current_page_index, state,
        )
        self._viewer.set_state(state)

        status = "excluida" if page.is_excluded else "incluida"
        self._status_bar.showMessage(f"Página {status}", 2000)

    def _on_rotate_90(self) -> None:
        """Rota la página actual 90° en sentido horario y ajusta coords de barcodes."""
        if self._current_page_index < 0:
            return
        page = self._pages[self._current_page_index]

        image = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            return

        img_h, img_w = image.shape[:2]

        rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        cv2.imwrite(page.image_path, rotated)

        # Rotar coordenadas de barcodes: (x, y, w, h) -> 90° CW
        # Nuevo sistema: new_x = img_h - y - h, new_y = x, new_w = h, new_h = w
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            db_page = page_repo.get_by_id(page.id)
            if db_page:
                for bc in db_page.barcodes:
                    old_x, old_y = bc.pos_x, bc.pos_y
                    old_w, old_h = bc.pos_w, bc.pos_h
                    bc.pos_x = img_h - old_y - old_h
                    bc.pos_y = old_x
                    bc.pos_w = old_h
                    bc.pos_h = old_w
                session.commit()

        self._navigate_to(self._current_page_index)

    def _determine_current_state(self, page: Page) -> PageState:
        """Calcula el PageState de una página considerando is_excluded."""
        barcodes = []
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            db_page = page_repo.get_by_id(page.id)
            if db_page:
                barcodes = list(db_page.barcodes)
        return determine_page_state(
            needs_review=page.needs_review,
            barcodes=barcodes,
            ai_fields_json=page.ai_fields_json,
            is_excluded=page.is_excluded,
        )

    def _on_delete_current_page(self) -> None:
        """Elimina solo la página actual."""
        if self._current_page_index < 0:
            return

        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            "¿Eliminar la página actual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        page = self._pages[self._current_page_index]
        images_dir = APP_IMAGES_DIR

        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            svc.remove_page(page.id)
            session.commit()

        self._reload_pages()
        self._thumbnail_panel.clear()
        for i, p in enumerate(self._pages):
            img = cv2.imread(p.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                state = determine_page_state(
                    needs_review=p.needs_review,
                    ai_fields_json=p.ai_fields_json,
                    is_excluded=p.is_excluded,
                )
                self._thumbnail_panel.add_thumbnail(i, img, state)

        if self._pages:
            idx = min(self._current_page_index, len(self._pages) - 1)
            self._navigate_to(idx)
        else:
            self._current_page_index = -1
            self._viewer.clear()
        self._update_page_info()

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
        images_dir = APP_IMAGES_DIR

        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            for page in pages_to_delete:
                svc.remove_page(page.id)
            session.commit()

        self._reload_pages()
        self._thumbnail_panel.clear()
        for i, page in enumerate(self._pages):
            img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                state = determine_page_state(
                    needs_review=page.needs_review,
                    ai_fields_json=page.ai_fields_json,
                    is_excluded=page.is_excluded,
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
    # Barcode manual
    # ==================================================================

    def _on_insert_barcode(self) -> None:
        """Placeholder para insertar barcode manual."""
        self._status_bar.showMessage(
            "Insertar barcode manual: pendiente de implementar", 3000,
        )

    def _on_delete_barcode(self) -> None:
        """Placeholder para eliminar barcode seleccionado."""
        self._status_bar.showMessage(
            "Eliminar barcode: pendiente de implementar", 3000,
        )

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

        app_ctx = self._build_app_context()
        batch_ctx = self._build_batch_context()

        self._recognition_worker = RecognitionWorker(
            executor=self._executor,
            app_context=app_ctx,
            batch_context=batch_ctx,
        )
        self._recognition_worker.page_processed.connect(
            self._on_page_processed,
        )
        self._recognition_worker.all_processed.connect(
            lambda: self._status_bar.showMessage(
                "Re-procesado completado", 3000,
            ),
        )
        self._recognition_worker.start()
        self._recognition_worker.enqueue_page(
            self._current_page_index, image,
        )
        self._recognition_worker.signal_no_more_pages()
        self._status_bar.showMessage("Re-procesando página...")

    # ==================================================================
    # Builders de contextos (reutilizables)
    # ==================================================================

    def _build_app_context(self) -> AppContext:
        """Construye un AppContext enriquecido desde la aplicación cargada."""
        app = self._application
        if app is None:
            return AppContext(id=self._app_id)
        return AppContext(
            id=self._app_id,
            name=app.name,
            description=app.description,
            config=json.loads(app.ai_config_json or "{}"),
            batch_fields_def=json.loads(app.batch_fields_json or "[]"),
            transfer_config=json.loads(app.transfer_json or "{}"),
            auto_transfer=app.auto_transfer,
            output_format=app.output_format or "tiff",
        )

    def _build_batch_context(self) -> BatchContext:
        """Construye un BatchContext enriquecido desde la BD."""
        if not self._batch_id:
            return BatchContext()
        try:
            from app.db.repositories.batch_repo import BatchRepository
            with self._session_factory() as session:
                repo = BatchRepository(session)
                batch = repo.get_by_id(self._batch_id)
                if batch is None:
                    return BatchContext(id=self._batch_id)
                return BatchContext(
                    id=batch.id,
                    fields=json.loads(batch.fields_json or "{}"),
                    state=batch.state,
                    page_count=batch.page_count,
                    folder_path=batch.folder_path or "",
                    hostname=batch.hostname or "",
                )
        except Exception:
            return BatchContext(id=self._batch_id)

    # ==================================================================
    # Eventos de ciclo de vida
    # ==================================================================

    def _fire_event(self, event_name: str, **extra_ctx) -> Any:
        """Ejecuta un entry point de ciclo de vida."""
        app_ctx = self._build_app_context()
        batch_ctx = self._build_batch_context()

        return self._script_engine.run_event(
            script_id=event_name,
            entry_point=event_name,
            app=app_ctx,
            batch=batch_ctx,
            **extra_ctx,
        )

    # ==================================================================
    # Contadores y origen
    # ==================================================================

    def _update_lot_counters(self) -> None:
        """Actualiza los contadores del panel de barcodes."""
        if self._batch_id is None:
            return
        with self._session_factory() as session:
            svc = BatchService(session, APP_IMAGES_DIR)
            stats = svc.get_stats(self._batch_id)

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
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt as QtCore_Qt

        self._combo_source.clear()
        if scanner_checked:
            self._status_bar.showMessage("Buscando escáneres…")
            QApplication.setOverrideCursor(QtCore_Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            try:
                scanner = self._get_scanner()
                sources = scanner.list_sources()
                self._combo_source.addItems(sources)
                if sources:
                    self._status_bar.showMessage(
                        f"{len(sources)} escáner(es) encontrado(s)", 3000,
                    )
                else:
                    self._status_bar.showMessage(
                        "No se encontraron escáneres", 5000,
                    )
            except Exception as e:
                log.warning("No se pudieron listar escáneres: %s", e)
                self._status_bar.showMessage(
                    "Error al buscar escáneres", 5000,
                )
            finally:
                QApplication.restoreOverrideCursor()
        else:
            self._combo_source.setPlaceholderText(
                "Usa el botón para seleccionar archivo...",
            )
            self._status_bar.clearMessage()

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
            self._fire_event("on_key_event", key=key_str)
        super().keyPressEvent(event)

    # ==================================================================
    # Resize — reposicionar overlay
    # ==================================================================

    def resizeEvent(self, event) -> None:
        """Reposiciona el overlay del visor al redimensionar."""
        super().resizeEvent(event)
        self._reposition_overlay()

    def showEvent(self, event) -> None:
        """Posiciona el overlay cuando la ventana se muestra."""
        super().showEvent(event)
        self._reposition_overlay()

    def _reposition_overlay(self) -> None:
        """Centra el overlay en la parte inferior del visor."""
        viewer = self._viewer
        overlay = self._viewer_overlay
        overlay.adjustSize()
        ow = overlay.sizeHint().width()
        oh = overlay.sizeHint().height()
        vw = viewer.width()
        vh = viewer.height()
        x = max(0, (vw - ow) // 2)
        y = max(0, vh - oh - 10)
        overlay.move(x, y)

    # ==================================================================
    # Drag & drop
    # ==================================================================

    _IMPORT_SUFFIXES = {
        ".pdf", ".tiff", ".tif", ".jpg", ".jpeg", ".png", ".bmp",
    }

    def dragEnterEvent(self, event) -> None:
        """Acepta drag de archivos importables."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    suffix = Path(url.toLocalFile()).suffix.lower()
                    if suffix in self._IMPORT_SUFFIXES:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event) -> None:
        """Importa los archivos soltados."""
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = url.toLocalFile()
                if Path(p).suffix.lower() in self._IMPORT_SUFFIXES:
                    paths.append(p)
        if paths:
            event.acceptProposedAction()
            self._import_paths(paths)

    # ==================================================================
    # Cierre
    # ==================================================================

    def closeEvent(self, event) -> None:
        """Detiene workers y ejecuta on_app_end."""
        for worker in (
            self._scan_worker,
            self._recognition_worker,
            self._transfer_worker,
        ):
            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.wait(3000)

        self._fire_event("on_app_end")
        self._metadata_panel.cleanup()
        if self._scanner is not None:
            try:
                self._scanner.close()
            except Exception:
                pass
            self._scanner = None
        self.closed.emit()
        super().closeEvent(event)
