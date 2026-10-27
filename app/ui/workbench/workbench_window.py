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
from PySide6.QtCore import QSize, Qt, Signal, QSettings
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
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
from app.pipeline.page_context import persist_separator, separator_state
from app.services.barcode_service import BarcodeService
from app.services.batch_service import BatchService
from app.services.image_pipeline import ImagePipelineService
from app.services.import_service import ImportService
from app.services.ocr_service import OcrService
from app.services.script_engine import ScriptEngine
from app.models.image_config import ImageConfig, parse_image_config
from app.models.workbench_layout import BARCODES, WorkbenchLayout
from app.services.transfer_flow import (
    compile_transfer_scripts,
    transfer_page_dict,
    validate_before_transfer,
)
from app.services.transfer_service import TransferService, parse_transfer_config
from app.ui.workbench.barcode_panel import BarcodePanel
from app.ui.workbench.document_viewer import DocumentViewer
from app.ui.workbench.metadata_panel import MetadataPanel
from app.ui.workbench.scan_config_popup import ScanConfigPopup
from app.ui.workbench.page_state import (
    PageState,
    determine_page_state,
)
from app.ui.workbench.thumbnail_panel import ThumbnailPanel
from app.ui.workbench.viewer_overlay import ViewerOverlay
from app.ui.icons import icon as lucide_icon
from app.ui.palette import color as palette_color
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    PageContext,
    RecognitionWorker,
)
from app.services.scanner_service import ScanConfig
from app.ui.workbench.scanner_config_dialog import ScannerConfigDialog
from app.workers.scan_worker import ScanWorker
from app.workers.transfer_worker import TransferWorker
from config.settings import APP_DATA_DIR, APP_IMAGES_DIR  # noqa: F401  # APP_DATA_DIR parcheado por tests

log = logging.getLogger(__name__)


def format_lot_counters(stats: dict[str, int], tr: Any = lambda t: t) -> str:
    """Texto de los contadores del lote para la barra de estado."""
    return tr(
        "{0} páginas · {1} con barcode · {2} separadores · {3} a revisión"
    ).format(
        stats.get("total_pages", 0),
        stats.get("with_barcode", 0),
        stats.get("separators", 0),
        stats.get("needs_review", 0),
    )


def format_processed(done: int, total: int, errors: int, tr: Any = lambda t: t) -> str:
    """«Procesado N/M» al terminar el pipeline, como Flexibar."""
    suffix = tr(" ({0} errores)").format(errors) if errors else ""
    return tr("Procesado {0}/{1}{2}").format(done, total, suffix)


def format_image_info(width: int, height: int, dpi: int | None) -> str:
    """Tamaño y resolución de la página del visor («1240×1754 — 150 DPI»)."""
    size = f"{width}\u00d7{height}"
    return f"{size} \u2014 {dpi} DPI" if dpi else size


MIN_PLAUSIBLE_DPI = 50


def read_dpi(image_path: str | Path) -> int | None:
    """DPI guardados en la imagen, o None. Solo lee la cabecera."""
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            dpi = img.info.get("dpi")
    except (OSError, ValueError) as e:
        log.debug("Sin DPI para %s: %s", image_path, e)
        return None
    if not dpi:
        return None
    value = round(float(dpi[0]))
    # cv2.imwrite deja los TIFF con resolución 1: eso no es un dato real.
    return value if value >= MIN_PLAUSIBLE_DPI else None


def page_review_message(
    needs_review: bool,
    review_reason: str,
    processing_errors_json: str,
    script_errors_json: str,
    tr: Any = lambda t: t,
) -> str:
    """Motivo de revisión y errores de una página, para la barra de estado."""

    def _count(raw: str) -> int:
        try:
            data = json.loads(raw or "[]")
        except json.JSONDecodeError, TypeError:
            return 0
        return len(data) if isinstance(data, list) else 0

    errors = _count(processing_errors_json) + _count(script_errors_json)
    if not needs_review and not errors:
        return ""
    parts = []
    if needs_review:
        parts.append(
            tr("A revisión: {0}").format(review_reason)
            if review_reason
            else tr("Página a revisión")
        )
    if errors:
        parts.append(tr("{0} error(es) de procesado; detalle en el Log").format(errors))
    return " · ".join(parts)


def _barcode_snapshot(barcode: Barcode) -> dict[str, Any]:
    """Datos de un barcode para recrearlo al deshacer su borrado."""
    return {
        name: getattr(barcode, name)
        for name in (
            "page_id",
            "value",
            "symbology",
            "engine",
            "step_id",
            "quality",
            "pos_x",
            "pos_y",
            "pos_w",
            "pos_h",
            "role",
        )
    }


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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._app_id = app_id
        self._session_factory = session_factory

        # Estado interno
        self._application: Application | None = None
        self._batch_id: int | None = None
        self._pages: list[Page] = []
        self._current_page_index: int = -1
        # Pila de deshacer de la edición de barcodes (Ctrl+Z), por sesión de
        # lote, como el BarcodeSession de FlexibarNET10.
        self._barcode_undo: list[dict[str, Any]] = []

        # Servicios
        self._script_engine = ScriptEngine()
        self._image_service = ImagePipelineService()
        self._barcode_service = BarcodeService()
        self._ocr_service = OcrService()
        self._import_service = ImportService()
        self._transfer_service = TransferService()
        self._scanner: Any = None  # Instancia reutilizable de BaseScanner
        self._last_scan_options: dict[str, Any] = {}  # Opciones del último escaneo
        self._executor: PipelineExecutor | None = None

        # Workers
        self._scan_worker: ScanWorker | None = None
        self._recognition_worker: RecognitionWorker | None = None
        self._transfer_worker: TransferWorker | None = None

        # Panel de verificación (se configura después de UI)
        self._verification_panel = None

        # Inicializar
        self._load_application()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_verification_panel()

        self._restore_source_settings()

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
            ocr_service=self._ocr_service,
        )

    def _compile_events(self) -> None:
        """Pre-compila los scripts de eventos del ciclo de vida."""
        try:
            events = json.loads(self._application.events_json)
        except json.JSONDecodeError, TypeError:
            events = {}

        for event_name, source in events.items():
            if source and source.strip():
                try:
                    self._script_engine.compile_script(
                        event_name,
                        source,
                        label=event_name,
                    )
                except Exception as e:
                    log.warning(
                        "Error compilando evento '%s': %s",
                        event_name,
                        e,
                    )

        compile_transfer_scripts(
            self._script_engine,
            parse_transfer_config(self._application.transfer_json or "{}"),
        )

    def _setup_ui(self) -> None:
        """Construye toda la interfaz gráfica."""
        app_name = self._application.name if self._application else "Workbench"
        self.setWindowTitle(self.tr("DocScan Studio \u2014 {0}").format(app_name))
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)
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

        # Panel central: visor y, debajo, su barra de herramientas
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._viewer = DocumentViewer()
        center_layout.addWidget(self._viewer, stretch=1)

        # La barra va en su propia franja bajo el visor, no flotando sobre
        # él: encima tapaba la parte inferior de la página (como en
        # FlexibarNET10, la barra del visor queda siempre fuera de la imagen).
        viewer_bar = QWidget()
        viewer_bar.setObjectName("viewerBar")
        viewer_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar_layout = QHBoxLayout(viewer_bar)
        bar_layout.setContentsMargins(0, 4, 0, 4)
        self._viewer_overlay = ViewerOverlay()
        bar_layout.addStretch(1)
        bar_layout.addWidget(self._viewer_overlay)
        bar_layout.addStretch(1)
        center_layout.addWidget(viewer_bar)

        # Panel derecho (paridad FlexibarNET10): barcodes de la página y
        # campos de lote arriba, con alto según contenido y tope; las
        # pestañas Verificación / OCR / Log ocupan el resto.
        right_widget = QWidget()
        right_widget.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._barcode_panel = BarcodePanel()
        self._metadata_panel = MetadataPanel()

        right_layout.addWidget(self._barcode_panel)
        right_layout.addWidget(self._metadata_panel, stretch=1)

        # Armar splitter
        self._splitter.addWidget(self._thumbnail_panel)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 0)  # miniaturas: ancho fijo
        self._splitter.setStretchFactor(1, 7)  # visor: máximo
        self._splitter.setStretchFactor(2, 2)  # derecha: menor
        # Tamaños iniciales en píxeles: miniaturas 170, visor 750, derecha 300
        self._splitter.setSizes([170, 750, 300])

        main_layout.addWidget(self._splitter)

        # --- Status bar con barra de progreso ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Contadores del lote: antes ocupaban un grupo del panel derecho; van
        # a la barra de estado, como el «Procesado 5/5» de FlexibarNET10.
        self._lbl_counters = QLabel()
        self._lbl_counters.setObjectName("statusCounters")
        self._status_bar.addPermanentWidget(self._lbl_counters)

        # Tamaño y DPI de la página del visor, y barra de progreso fina de
        # 120×3 px a la derecha, como Flexibar.
        self._lbl_image_info = QLabel()
        self._lbl_image_info.setObjectName("statusImageInfo")
        self._status_bar.addPermanentWidget(self._lbl_image_info)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("statusProgress")
        self._progress_bar.setFixedSize(120, 3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)
        # Progreso y errores de la pasada del pipeline en curso
        self._run_progress: tuple[int, int] = (0, 0)
        self._run_errors = 0

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
        """Barra superior como la de FlexibarNET 10.

        Escanear (F5) · ⚙ escáner · distintivo del escáner · Importar… (Ctrl+I)
        | Procesar (F9) | Transferir (Ctrl+T) · Cerrar lote; a la derecha,
        tema y tamaño de letra.
        """
        toolbar = QToolBar(self.tr("Workbench"))
        toolbar.setObjectName("workbenchToolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # (botón, icono Lucide, rol de color) para repintar al cambiar de tema
        self._toolbar_icons: list[tuple[QPushButton, str, str]] = []

        self._btn_scan = self._toolbar_button(
            self.tr("Escanear"),
            "scan-line",
            "on_accent",
            self.tr("Escanear (F5)"),
            css_class="primary",
        )
        toolbar.addWidget(self._btn_scan)

        self._scan_popup = ScanConfigPopup(self)
        self._combo_source = self._scan_popup.combo_source
        self._combo_source_type = self._scan_popup.combo_source_type
        self._chk_scanner_config = self._scan_popup.chk_show_options
        self._btn_scan_config = self._toolbar_button(
            "",
            "settings",
            "text",
            self.tr("Configurar el escáner"),
        )
        self._btn_scan_config.setObjectName("scanConfigButton")
        toolbar.addWidget(self._btn_scan_config)

        # Indicador «Escáner: …» (el «Perfil: …» de Flexibar): una píldora
        # pequeña centrada, no un botón más.
        chip_box = QWidget()
        chip_box.setObjectName("scannerChipBox")
        chip_layout = QHBoxLayout(chip_box)
        chip_layout.setContentsMargins(0, 0, 6, 0)
        chip_layout.setSpacing(4)
        lbl_chip_title = QLabel(self.tr("Esc\u00e1ner:"))
        lbl_chip_title.setObjectName("scannerChipTitle")
        chip_layout.addWidget(lbl_chip_title, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl_scanner = QLabel()
        self._lbl_scanner.setObjectName("scannerChip")
        self._lbl_scanner.setToolTip(
            self.tr("Esc\u00e1ner y fuente con los que se captura")
        )
        chip_layout.addWidget(self._lbl_scanner, 0, Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(chip_box)

        self._btn_import = self._toolbar_button(
            self.tr("Importar…"),
            "download",
            "text",
            self.tr("Importar archivos al lote actual (Ctrl+I)"),
        )
        toolbar.addWidget(self._btn_import)
        toolbar.addSeparator()

        self._btn_process = self._toolbar_button(
            self.tr("Procesar"),
            "play",
            "text",
            self.tr("Procesar todas las páginas del lote (F9)"),
        )
        toolbar.addWidget(self._btn_process)
        toolbar.addSeparator()

        self._btn_transfer = self._toolbar_button(
            self.tr("Transferir"),
            "arrow-up-to-line",
            "success",
            self.tr("Transferir el lote (Ctrl+T)"),
            css_class="success-outline",
        )
        toolbar.addWidget(self._btn_transfer)

        self._btn_close_batch = self._toolbar_button(
            self.tr("Cerrar lote"),
            "x",
            "danger",
            self.tr("Cerrar el lote sin transferir (Ctrl+W)"),
            css_class="danger-outline",
        )
        toolbar.addWidget(self._btn_close_batch)

        # Spacer
        spacer = QWidget()
        spacer.setObjectName("toolbarSpacer")
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        # Toggle tema
        from app.ui.theme_manager import ThemeManager

        self._theme_manager = ThemeManager()
        self._btn_theme = QPushButton()
        self._btn_theme.setToolTip(self.tr("Cambiar tema claro/oscuro"))
        self._update_theme_button()
        toolbar.addWidget(self._btn_theme)

        from app.ui.icon_factory import icon_font_decrease, icon_font_increase

        icon_color = palette_color("text")

        self._btn_font_up = QPushButton()
        self._btn_font_up.setIcon(icon_font_increase(icon_color, 32))
        self._btn_font_up.setToolTip(self.tr("Aumentar tama\u00f1o de fuente"))
        self._btn_font_up.setFixedSize(34, 34)
        self._btn_font_down = QPushButton()
        self._btn_font_down.setIcon(icon_font_decrease(icon_color, 32))
        self._btn_font_down.setToolTip(self.tr("Reducir tama\u00f1o de fuente"))
        self._btn_font_down.setFixedSize(34, 34)
        toolbar.addWidget(self._btn_font_up)
        toolbar.addWidget(self._btn_font_down)

    def _toolbar_button(
        self,
        text: str,
        icon_name: str,
        role: str,
        tooltip: str,
        *,
        css_class: str = "",
    ) -> QPushButton:
        """Botón de la barra superior con icono Lucide del color ``role``."""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setIconSize(QSize(16, 16))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if css_class:
            btn.setProperty("cssClass", css_class)
        btn.setIcon(lucide_icon(icon_name, role, 16))
        self._toolbar_icons.append((btn, icon_name, role))
        return btn

    def _update_toolbar_icons(self) -> None:
        for btn, icon_name, role in self._toolbar_icons:
            btn.setIcon(lucide_icon(icon_name, role, 16))
        self._scan_popup.refresh_icons()

    def _update_theme_button(self) -> None:
        from app.ui.icon_factory import icon_moon, icon_sun

        if self._theme_manager.is_dark:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_sun())
        else:
            self._btn_theme.setText("")
            self._btn_theme.setIcon(icon_moon(palette_color("subtext0")))

    def _connect_signals(self) -> None:
        """Conecta todas las señales de la UI."""
        # Procesar / Transferir / Cerrar lote
        self._btn_scan.clicked.connect(self._on_scan)
        self._btn_scan_config.clicked.connect(self._on_scan_config)
        self._btn_import.clicked.connect(self._on_import)
        self._btn_process.clicked.connect(self._on_process_all)
        self._scan_popup.refresh_requested.connect(self._refresh_scanners)
        self._scan_popup.config_changed.connect(self._update_scanner_chip)
        self._btn_transfer.clicked.connect(self._on_transfer)
        self._btn_close_batch.clicked.connect(self._on_close_batch)

        # Origen

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
        self._viewer_overlay.nav_next_barcode.connect(self._on_next_barcode)
        self._viewer_overlay.nav_next_review.connect(self._on_next_review)
        self._viewer_overlay.nav_script.connect(self._on_nav_script)
        self._viewer_overlay.page_jump_requested.connect(self._on_page_jump)

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
        # Fila ↔ recuadro del visor, en los dos sentidos.
        self._barcode_panel.row_hovered.connect(self._viewer.highlight_barcode)
        self._viewer.barcode_hovered.connect(self._barcode_panel.highlight_row)

    def _setup_shortcuts(self) -> None:
        """Atajos de teclado del workbench."""
        _s = lambda keys, slot: QShortcut(
            QKeySequence(keys),
            self,
        ).activated.connect(slot)

        # Navegación. Las teclas simples pasan por _typing_guard: mientras
        # se teclea en el contador de página del overlay, el atajo de
        # ventana tendría prioridad sobre el campo de texto (y "Supr"
        # llegaría a borrar una página en lugar de un dígito).
        _s("Left", self._typing_guard(self._on_prev))
        _s("Right", self._typing_guard(self._on_next))
        _s("Home", self._typing_guard(self._on_first))
        _s("End", self._typing_guard(self._on_last))
        _s("Ctrl+Right", self._on_next_barcode)
        _s("Ctrl+Shift+Right", self._on_next_review)
        _s("Ctrl+G", self._on_nav_script)

        # Zoom
        _s("Ctrl++", self._viewer.zoom_in)
        _s("Ctrl+=", self._viewer.zoom_in)
        _s("Ctrl+-", self._viewer.zoom_out)
        _s("Ctrl+F", self._viewer.fit_to_page)
        _s("Ctrl+0", self._on_zoom_100)

        # Adquisición y transferencia
        _s("F5", self._on_scan)
        _s("Ctrl+I", self._on_import)
        _s("F9", self._on_process_all)
        _s("Ctrl+T", self._on_transfer)
        _s("Ctrl+W", self._on_close_batch)

        # Manipulación de página
        _s("Ctrl+R", self._on_rotate_90)
        _s("Ctrl+M", self._on_mark_page)
        _s("Delete", self._typing_guard(self._on_delete_current_page))
        _s("Ctrl+P", self._on_reprocess_page)
        # Barcodes (paridad FlexibarNET10): añadir con Ctrl+N / Insert,
        # deshacer con Ctrl+Z. Supr sobre una fila enfocada la borra (lo
        # gestiona la propia fila). Ctrl+B se conserva por compatibilidad.
        _s("Ctrl+B", self._not_typing(self._on_insert_barcode))
        _s("Ctrl+N", self._not_typing(self._on_insert_barcode))
        _s("Insert", self._not_typing(self._on_insert_barcode))
        _s("Ctrl+Z", self._not_typing(self._on_undo_barcode))

    def _typing_guard(self, slot: Any) -> Any:
        """Envuelve un slot para que no se dispare mientras se escribe.

        Args:
            slot: Callable del atajo original.

        Returns:
            Callable que ignora la pulsación si el contador de página
            tiene el foco de teclado.
        """

        def _guarded() -> None:
            if self._viewer_overlay.is_editing_page():
                return
            slot()

        return _guarded

    def _not_typing(self, slot: Any) -> Any:
        """Envuelve un atajo para que no actúe mientras se escribe en un campo."""
        from PySide6.QtWidgets import (
            QAbstractSpinBox,
            QApplication,
            QLineEdit,
            QPlainTextEdit,
            QTextEdit,
        )

        def _guarded() -> None:
            focus = QApplication.focusWidget()
            if isinstance(
                focus, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)
            ):
                return
            slot()

        return _guarded

    def _call_verification_hook(self, method: str, *args: Any) -> Any:
        """Llama a un hook del panel de verificación con aislamiento de errores."""
        if not self._verification_panel:
            return None
        try:
            return getattr(self._verification_panel, method)(*args)
        except Exception as e:
            log.error("Error en verification_panel.%s: %s", method, e)
            return None

    def _setup_verification_panel(self) -> None:
        """Carga e instancia el panel de verificación si está definido."""
        if self._application is None:
            return
        try:
            events = json.loads(self._application.events_json or "{}")
        except json.JSONDecodeError, TypeError:
            return

        source = events.get("verification_panel", "").strip()
        if not source:
            return

        from app.ui.workbench.verification_panel import (
            VerificationPanel,
            WorkbenchAPI,
        )

        # Compilar el script
        try:
            code = compile(source, "<verification_panel>", "exec")
        except SyntaxError as e:
            log.error("Error de sintaxis en verification_panel: %s", e)
            return

        # Ejecutar en namespace aislado con acceso a PySide6
        import PySide6.QtWidgets as QtWidgets
        import PySide6.QtCore as QtCore
        import PySide6.QtGui as QtGui

        namespace: dict[str, Any] = {
            "__builtins__": __builtins__,
            "VerificationPanel": VerificationPanel,
            "WorkbenchAPI": WorkbenchAPI,
            "QtWidgets": QtWidgets,
            "QtCore": QtCore,
            "QtGui": QtGui,
            "log": logging.getLogger("verification_panel"),
            "json": json,
            "re": __import__("re"),
            "datetime": __import__("datetime"),
            "Path": __import__("pathlib").Path,
            "http": __import__("httpx"),
        }

        try:
            exec(code, namespace)  # noqa: S102
        except Exception as e:
            log.error("Error ejecutando verification_panel: %s", e)
            return

        # Buscar la subclase de VerificationPanel
        panel_classes = [
            obj
            for obj in namespace.values()
            if isinstance(obj, type)
            and issubclass(obj, VerificationPanel)
            and obj is not VerificationPanel
        ]

        if not panel_classes:
            log.warning(
                "verification_panel no define una subclase de VerificationPanel"
            )
            return

        if len(panel_classes) > 1:
            log.warning(
                "verification_panel define %d subclases, usando la última: %s",
                len(panel_classes),
                panel_classes[-1].__name__,
            )
        panel_class = panel_classes[-1]

        # Construir API y panel
        api = WorkbenchAPI(
            session_factory=self._session_factory,
            get_pages=lambda: self._pages,
            get_batch_id=lambda: self._batch_id,
            get_current_index=lambda: self._current_page_index,
            navigate_fn=self._navigate_to,
            log_fn=lambda msg: log.info("[Verificación] %s", msg),
            get_batch_fields_fn=self._metadata_panel.get_batch_fields,
            set_batch_field_fn=lambda n, v: self._on_batch_field_changed(n, v),
        )

        try:
            self._verification_panel = panel_class(api, parent=self)
            self._metadata_panel.add_verification_tab(self._verification_panel)
            log.info("Panel de verificación cargado: %s", panel_class.__name__)
        except Exception as e:
            log.error("Error instanciando panel de verificación: %s", e)
            self._verification_panel = None

    def _configure_metadata(self) -> None:
        """Configura los campos de lote e indexación según la app."""
        if self._application is None:
            return
        try:
            raw_batch = json.loads(self._application.batch_fields_json)
        except json.JSONDecodeError, TypeError:
            raw_batch = []
        try:
            index_fields = json.loads(self._application.index_fields_json)
        except json.JSONDecodeError, TypeError:
            index_fields = []

        # Mapear formato tab_batch_fields → MetadataPanel.configure()
        type_map = {
            "texto": "Texto",
            "fecha": "Fecha",
            "lista": "Lista",
            "numérico": "Número",
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

        # Orden y visibilidad del panel derecho, por aplicación.
        layout = WorkbenchLayout.from_json(
            getattr(self._application, "workbench_layout_json", "") or ""
        )
        self._metadata_panel.apply_layout(layout)
        self._barcode_panel.setVisible(layout.is_visible(BARCODES))
        self._barcode_panel.set_add_button_visible(not self._add_barcode_hidden())

    def _add_barcode_hidden(self) -> bool:
        """¿La aplicación oculta «+ Añadir» barcode (y sus atajos)?"""
        return bool(getattr(self._application, "hide_add_barcode_button", False))

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
        self._update_toolbar_icons()

    def _update_font_icons(self) -> None:
        from app.ui.icon_factory import icon_font_decrease, icon_font_increase

        color = palette_color("text")
        self._btn_font_up.setIcon(icon_font_increase(color, 32))
        self._btn_font_down.setIcon(icon_font_decrease(color, 32))

    def _update_overlay_icons(self) -> None:
        color = palette_color("text")
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
            # Buscar el lote más reciente que esté en curso (no cerrado ni transferido)
            # "verified" = cerrado manualmente por el usuario → no restaurar
            for b in batches:
                if b.state in ("created", "read", "ready_to_export"):
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
            self._barcode_undo.clear()

        self._pages = []
        self._current_page_index = -1
        self._update_page_info()
        self._status_bar.showMessage(
            self.tr("Lote {0} creado").format(self._batch_id),
            3000,
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
            self._barcode_undo.clear()
            batch_fields = json.loads(batch.fields_json or "{}")

        self._metadata_panel.set_batch_fields(batch_fields)

        self._reload_pages()
        self._thumbnail_panel.clear()
        for i, page in enumerate(self._pages):
            img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                state = determine_page_state(
                    needs_review=page.needs_review,
                    fields_json=page.index_fields_json,
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
            self.tr("Lote {0} cargado ({1} p\u00e1ginas)").format(
                self._batch_id,
                len(self._pages),
            ),
            3000,
        )

        self._call_verification_hook("on_batch_loaded")
        self._fire_event("on_batch_loaded")

        # Reanudar pipeline para páginas no procesadas
        self._resume_pending_pipeline()

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

    def _acquisition_running(self) -> bool:
        """Avisa y devuelve True si ya hay una adquisición en curso."""
        if self._scan_worker and self._scan_worker.isRunning():
            QMessageBox.information(
                self,
                self.tr("En proceso"),
                self.tr("Ya hay un proceso de adquisición en curso."),
            )
            return True
        return False

    def _set_acquire_enabled(self, enabled: bool) -> None:
        """Escanear, Importar y Procesar se bloquean mientras corre el pipeline."""
        for btn in (self._btn_scan, self._btn_import, self._btn_process):
            btn.setEnabled(enabled)

    def _on_scan(self) -> None:
        """Escanear (F5)."""
        if not self._btn_scan.isEnabled() or self._acquisition_running():
            return
        self._start_scanner()

    def _on_import(self) -> None:
        """Importar… (Ctrl+I)."""
        if not self._btn_import.isEnabled() or self._acquisition_running():
            return
        self._start_import()

    def _on_scan_config(self) -> None:
        """Abre el popover ⚙ con el escáner, la fuente y «mostrar opciones»."""
        if not self._scan_popup.scanners_listed:
            self._refresh_scanners()
        self._scan_popup.show_below(self._btn_scan_config)

    def _refresh_scanners(self) -> None:
        """Enumera los escáneres disponibles (puede tardar unos segundos)."""
        from PySide6.QtWidgets import QApplication

        self._status_bar.showMessage(self.tr("Buscando escáneres…"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        sources: list[str] = []
        try:
            sources = list(self._get_scanner().list_sources())
            if sources:
                self._status_bar.showMessage(
                    self.tr("{0} escáner(es) encontrado(s)").format(len(sources)),
                    3000,
                )
            else:
                self._status_bar.showMessage(
                    self.tr("No se encontraron escáneres"),
                    5000,
                )
        except Exception as e:
            log.warning("No se pudieron listar escáneres: %s", e)
            self._status_bar.showMessage(
                self.tr("Error al buscar escáneres"),
                5000,
            )
        finally:
            QApplication.restoreOverrideCursor()
        self._scan_popup.set_scanners(sources)

    def _update_scanner_chip(self) -> None:
        self._lbl_scanner.setText(self._scan_popup.summary())

    def _on_process_all(self) -> None:
        """Procesar (F9): pasa el pipeline por todas las páginas del lote.

        Como «Procesar» de Flexibar: reprocesa el lote entero, no solo lo
        pendiente, y termina por el mismo camino que una captura.
        """
        if not self._btn_process.isEnabled():
            return
        if self._recognition_worker and self._recognition_worker.isRunning():
            self._status_bar.showMessage(
                self.tr("Ya hay un procesado en curso"),
                3000,
            )
            return
        if not self._pages or self._executor is None:
            self._status_bar.showMessage(
                self.tr("No hay páginas que procesar"),
                3000,
            )
            return
        self._run_pipeline_on(
            [(page.page_index, page) for page in self._pages],
            self.tr("Procesando {0} página(s)…"),
        )

    def _get_scanner(self) -> Any:
        """Devuelve la instancia reutilizable de escáner."""
        if self._scanner is None:
            from app.services.scanner_service import create_scanner

            self._scanner = create_scanner(
                self._application.scanner_backend if self._application else None,
            )
        return self._scanner

    def _start_scanner(self) -> None:
        """Inicia adquisición desde escáner."""
        source = self._combo_source.currentText()
        if not source and not self._scan_popup.scanners_listed:
            self._refresh_scanners()
            source = self._combo_source.currentText()
        if not source:
            QMessageBox.warning(
                self,
                self.tr("Sin esc\u00e1ner"),
                self.tr(
                    "No hay ning\u00fan esc\u00e1ner seleccionado. Elige uno en \u2699."
                ),
            )
            self._scan_popup.show_below(self._btn_scan_config)
            return

        try:
            scanner = self._get_scanner()
        except RuntimeError as e:
            QMessageBox.critical(self, self.tr("Error de esc\u00e1ner"), str(e))
            return

        source_type = self._combo_source_type.currentData() or "flatbed"
        scan_config = ScanConfig(source_type=source_type)

        # Aplicar opciones persistidas de la sesión anterior
        if self._last_scan_options:
            scan_config.extra_options = dict(self._last_scan_options)

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
            f"last_import_dir/{self._app_id}",
            str(Path.home()),
        )

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr("Importar documentos"),
            last_dir,
            "Documentos (*.pdf *.tiff *.tif *.jpg *.jpeg *.png *.bmp);;Todos (*)",
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
        self._scan_worker.cancelled.connect(self._on_scan_cancelled)
        self._scan_worker.error_occurred.connect(self._on_scan_error)

        # Conectar señales del recognition worker
        self._recognition_worker.page_processed.connect(
            self._on_page_processed,
        )
        self._recognition_worker.all_processed.connect(
            self._on_all_processed,
        )
        self._recognition_worker.cancelled.connect(self._on_processing_cancelled)
        self._recognition_worker.page_error.connect(self._on_page_error)
        self._recognition_worker.progress.connect(self._on_progress)

        # Mostrar progreso
        self._progress_bar.setValue(0)
        self._run_progress = (0, 0)
        self._run_errors = 0
        self._progress_bar.setVisible(True)
        self._set_acquire_enabled(False)

        # Arrancar
        self._recognition_worker.start()
        self._scan_worker.start()
        self._status_bar.showMessage(self.tr("Procesando..."))

    def _on_page_acquired(
        self,
        page_index: int,
        image: np.ndarray,
        source_path: str = "",
    ) -> None:
        """Una página ha sido adquirida: guardar, thumbnail, encolar."""
        images_dir = APP_IMAGES_DIR
        mode = getattr(self._scan_worker, "_mode", "") if self._scan_worker else ""

        image_config: ImageConfig | None = None

        if mode in ("scanner", "import_pdf"):
            # Escáner o PDF rasterizado: usar formato de app + ImageConfig
            output_format = (
                self._application.output_format if self._application else "tiff"
            )
            if self._application:
                config_json = (
                    getattr(
                        self._application,
                        "image_config_json",
                        "{}",
                    )
                    or "{}"
                )
                if config_json and config_json != "{}":
                    image_config = parse_image_config(config_json)
        else:
            # Importación de imagen: conservar formato original
            output_format = self._format_from_source(source_path)

        with self._session_factory() as session:
            svc = BatchService(session, images_dir)
            pages = svc.add_pages(
                self._batch_id,
                [image],
                output_format=output_format,
                image_config=image_config,
            )
            session.commit()
            for p in pages:
                session.refresh(p)
                session.expunge(p)
                self._pages.append(p)

        # Usar el page_index global asignado por la BD (no el local del worker)
        global_page_index = pages[0].page_index if pages else page_index

        # Añadir thumbnail
        self._thumbnail_panel.add_thumbnail(global_page_index, image)

        # Encolar para reconocimiento
        if self._recognition_worker:
            self._recognition_worker.enqueue_page(global_page_index, image)

        # Navegar a la página recién adquirida
        self._navigate_to(global_page_index)

        self._update_page_info()

    @staticmethod
    def _format_from_source(source_path: str) -> str:
        """Extrae el formato de salida a partir de la extensión del fichero origen."""
        if not source_path:
            return "tiff"
        ext = Path(source_path).suffix.lower()
        if ext in (".tif", ".tiff"):
            return "tiff"
        if ext in (".jpg", ".jpeg"):
            return "jpg"
        if ext == ".png":
            return "png"
        if ext == ".bmp":
            return "bmp"
        # Formato desconocido: TIFF sin pérdida como fallback
        return "tiff"

    def _on_scan_finished(self, total: int) -> None:
        """El escaneo/importación ha terminado."""
        log.info("Adquisición completada: %d páginas", total)
        if self._recognition_worker:
            self._recognition_worker.signal_no_more_pages()

    def _on_scan_cancelled(self, emitidas: int) -> None:
        """La adquisición se ha interrumpido antes de terminar.

        Se cierra la cola del reconocimiento para que no espere páginas
        que ya no van a llegar, pero **no** se trata como final correcto.
        """
        log.info("Adquisición cancelada tras %d páginas", emitidas)
        if self._recognition_worker:
            self._recognition_worker.signal_no_more_pages()

    def _on_processing_cancelled(self, procesadas: int, totales: int) -> None:
        """El reconocimiento se ha interrumpido con páginas pendientes.

        A diferencia de ``_on_all_processed``, no marca el lote como
        leído, no dispara ``on_scan_complete`` y no lanza la
        auto-transferencia: quedan páginas sin pasar por el pipeline.
        """
        if self._script_engine is None:
            return  # Ventana cerrada, ignorar señales tardías
        self._progress_bar.setVisible(False)
        self._set_acquire_enabled(True)
        self._reload_pages()
        self._update_lot_counters()
        log.warning("Procesamiento cancelado: %d de %d páginas", procesadas, totales)
        self._status_bar.showMessage(
            self.tr("Procesamiento cancelado: {0} de {1} páginas").format(
                procesadas, totales
            ),
            8000,
        )

    def _on_scan_error(self, error: str) -> None:
        """Error durante la adquisición."""
        self._progress_bar.setVisible(False)
        self._set_acquire_enabled(True)
        QMessageBox.critical(self, self.tr("Error de adquisici\u00f3n"), error)

    def _on_page_processed(self, page_index: int, page_ctx: Any) -> None:
        """Una página ha sido procesada por el pipeline."""
        if self._script_engine is None:
            return  # Ventana cerrada, ignorar señales tardías
        self._persist_page_results(page_index, page_ctx)

        state = determine_page_state(
            needs_review=page_ctx.flags.needs_review,
            barcodes=page_ctx.barcodes,
            fields_json=json.dumps(page_ctx.fields) if page_ctx.fields else "{}",
        )
        self._thumbnail_panel.update_thumbnail_state(page_index, state)

        # Actualizar imagen del thumbnail si un script la reemplazó
        if page_ctx.image_replaced and page_ctx.image is not None:
            self._thumbnail_panel.update_thumbnail_image(
                page_index,
                page_ctx.image,
            )

        # Si es la página actual, actualizar visor
        if page_index == self._current_page_index:
            if page_ctx.image_replaced and page_ctx.image is not None:
                self._viewer.set_image(page_ctx.image, state)
            else:
                self._viewer.set_state(state)
            self._viewer.set_overlays(
                barcodes=page_ctx.barcodes,
                fields=page_ctx.fields,
            )
            self._barcode_panel.set_page_barcodes(page_ctx.barcodes)
            self._reload_pages()
            if 0 <= page_index < len(self._pages):
                page = self._pages[page_index]
                self._metadata_panel.set_verification_data(
                    ocr_text=page.ocr_text,
                    fields_json=page.index_fields_json,
                    errors_json=page.processing_errors_json,
                    script_errors_json=page.script_errors_json,
                )

        self._call_verification_hook("on_pipeline_completed", page_index)

    def _persist_page_results(self, page_index: int, page_ctx: Any) -> None:
        """Guarda los resultados del pipeline en BD."""
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            page = page_repo.get_by_batch_and_index(self._batch_id, page_index)

            if page is None:
                log.warning("Página %d no encontrada en BD", page_index)
                return

            # Guardar imagen modificada solo si un script llamó a replace_image
            if (
                page_ctx.image_replaced
                and page_ctx.image is not None
                and page.image_path
            ):
                try:
                    from app.services.image_lib import ImageLib

                    original_dpi = ImageLib.get_dpi(page.image_path)
                    dpi_val = int(original_dpi[0]) if original_dpi[0] > 0 else None
                    ImageLib.save(
                        page_ctx.image,
                        page.image_path,
                        dpi=dpi_val,
                    )
                except Exception as e:
                    log.error("Error guardando imagen procesada: %s", e)

            # Deteccion de paginas en blanco
            blank_config = self._get_blank_config()
            if blank_config.get("blank_detection"):
                from app.services.image_pipeline import detect_blank

                test_image = page_ctx.image
                if test_image is None and page.image_path:
                    from app.services.image_lib import ImageLib

                    imgs = ImageLib.load(page.image_path)
                    test_image = imgs[0] if imgs else None
                if test_image is not None:
                    is_blank = detect_blank(
                        test_image,
                        content_threshold=blank_config.get(
                            "blank_content_threshold", 1.0
                        ),
                        white_tolerance=blank_config.get("blank_white_tolerance", 245),
                    )
                    page.is_blank = is_blank
                    if is_blank:
                        page.is_excluded = True

            page.pipeline_processed = True
            page.ocr_text = page_ctx.ocr_text or ""
            page.index_fields_json = (
                json.dumps(
                    page_ctx.fields,
                    ensure_ascii=False,
                )
                if page_ctx.fields
                else "{}"
            )
            page.needs_review = page_ctx.flags.needs_review
            page.review_reason = page_ctx.flags.review_reason
            persist_separator(page_ctx, page)
            page.processing_errors_json = json.dumps(
                page_ctx.flags.processing_errors,
                ensure_ascii=False,
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

    def _get_blank_config(self) -> dict:
        """Obtiene la configuracion de deteccion de blancos de la app."""
        if self._application and self._application.ai_config_json:
            try:
                return json.loads(self._application.ai_config_json)
            except json.JSONDecodeError, TypeError:
                pass
        return {}

    def _on_page_error(self, page_index: int, error: str) -> None:
        """Error procesando una página."""
        log.error("Error en página %d: %s", page_index, error)
        self._run_errors += 1
        self._thumbnail_panel.update_thumbnail_state(
            page_index,
            PageState.NEEDS_REVIEW,
        )

    def _on_all_processed(self) -> None:
        """Todo el pipeline ha terminado."""
        if self._script_engine is None:
            return  # Ventana cerrada, ignorar señales tardías
        self._progress_bar.setVisible(False)
        self._set_acquire_enabled(True)
        self._reload_pages()
        self._update_lot_counters()

        if self._batch_id:
            with self._session_factory() as session:
                svc = BatchService(session, APP_IMAGES_DIR)
                svc.transition_state(self._batch_id, "read")
                session.commit()

        self._fire_event("on_scan_complete")
        done, total = self._run_progress
        self._status_bar.showMessage(
            format_processed(done, total, self._run_errors, self.tr)
        )

        # Auto-transferencia (APP-02)
        if self._application and self._application.auto_transfer:
            self._on_transfer()

    def _on_progress(self, completed: int, total: int) -> None:
        """Actualiza la barra de progreso."""
        self._run_progress = (completed, total)
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(completed)

    def _resume_pending_pipeline(self) -> None:
        """Detecta páginas sin procesar y lanza el pipeline para ellas.

        Una página se considera no procesada si todos sus campos de
        resultado están en su valor por defecto (sin OCR, sin campos,
        sin barcodes, sin errores y sin marcas de revisión).
        """
        if not self._pages or self._executor is None:
            return

        pending: list[tuple[int, Page]] = []
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            for page in self._pages:
                db_page = page_repo.get_by_id(page.id)
                if db_page is None:
                    continue
                if not db_page.pipeline_processed:
                    pending.append((page.page_index, page))

        if not pending:
            return

        log.info(
            "Reanudando pipeline para %d página(s) no procesada(s)",
            len(pending),
        )
        self._run_pipeline_on(
            pending,
            self.tr("Procesando {0} p\u00e1gina(s) pendiente(s)..."),
        )

    def _run_pipeline_on(self, pages: list[tuple[int, Page]], message: str) -> None:
        """Pasa el pipeline por ``pages`` y termina en ``_on_all_processed``.

        Args:
            pages: Pares (índice de página, página) a procesar, en orden.
            message: Texto de la barra de estado; ``{0}`` es el número de páginas.
        """
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
            self._on_all_processed,
        )
        self._recognition_worker.cancelled.connect(self._on_processing_cancelled)
        self._recognition_worker.page_error.connect(self._on_page_error)
        self._recognition_worker.progress.connect(self._on_progress)

        self._progress_bar.setValue(0)
        self._run_progress = (0, 0)
        self._run_errors = 0
        self._progress_bar.setVisible(True)
        self._set_acquire_enabled(False)

        self._recognition_worker.start()

        for page_index, page in pages:
            img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                self._recognition_worker.enqueue_page(
                    page_index, img, separator_state(page)
                )

        self._recognition_worker.signal_no_more_pages()
        self._status_bar.showMessage(message.format(len(pages)))

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
                fields_json=page.index_fields_json,
                is_excluded=page.is_excluded,
            )

            try:
                idx_fields = json.loads(page.index_fields_json)
            except json.JSONDecodeError, TypeError:
                idx_fields = {}

            self._viewer.set_image(image, state)
            self._lbl_image_info.setText(
                format_image_info(
                    image.shape[1], image.shape[0], read_dpi(page.image_path)
                )
            )
            self._viewer.set_overlays(
                barcodes=barcodes,
                fields=idx_fields,
            )
            self._barcode_panel.set_page_barcodes(barcodes)
            self._metadata_panel.set_index_fields(idx_fields)
            self._metadata_panel.set_verification_data(
                ocr_text=page.ocr_text,
                fields_json=page.index_fields_json,
                errors_json=page.processing_errors_json,
                script_errors_json=page.script_errors_json,
            )
            review_message = page_review_message(
                page.needs_review,
                page.review_reason,
                page.processing_errors_json,
                page.script_errors_json,
                self.tr,
            )

        self._thumbnail_panel.set_current(page_index)
        if review_message:
            # El borde rojo dice que hay que revisar; aquí, por qué.
            self._status_bar.showMessage(review_message, 8000)
        self._update_page_info()

        self._call_verification_hook("on_page_changed", page_index)
        self._fire_event(
            "on_page_changed",
            page=self._build_page_context(page_index),
            page_index=page_index,
        )

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

    def _on_page_jump(self, page_index: int) -> None:
        """Salta a la página tecleada en el contador del visor.

        Args:
            page_index: Índice 0-based ya validado por el overlay.
        """
        if not self._pages or not 0 <= page_index < len(self._pages):
            return
        self._navigate_to(page_index)
        self._status_bar.showMessage(
            self.tr("Página {0} de {1}").format(page_index + 1, len(self._pages)),
            2000,
        )

    def _on_next_barcode(self) -> None:
        """Navega a la siguiente página que tenga barcodes."""
        if not self._pages:
            return
        start = self._current_page_index + 1
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            for i in range(start, len(self._pages)):
                db_page = page_repo.get_by_id(self._pages[i].id)
                if db_page and list(db_page.barcodes):
                    self._navigate_to(i)
                    return
        self._status_bar.showMessage(
            self.tr("No hay m\u00e1s p\u00e1ginas con barcode"), 3000
        )

    def _on_next_review(self) -> None:
        """Navega a la siguiente página pendiente de revisión."""
        if not self._pages:
            return
        start = self._current_page_index + 1
        for i in range(start, len(self._pages)):
            if self._pages[i].needs_review:
                self._navigate_to(i)
                return
        self._status_bar.showMessage(
            self.tr("No hay m\u00e1s p\u00e1ginas pendientes de revisi\u00f3n"),
            3000,
        )

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
                        {
                            "value": b.value,
                            "symbology": b.symbology,
                            "role": b.role or "",
                        }
                        for b in db_page.barcodes
                    ]
                pages_info.append(
                    {
                        "page_index": cached.page_index,
                        "barcodes": barcodes,
                        "needs_review": db_page.needs_review if db_page else False,
                    }
                )

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
                self.tr("Script de navegaci\u00f3n: sin destino"),
                2000,
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
                self,
                self.tr("Sin datos"),
                self.tr("No hay p\u00e1ginas para transferir."),
            )
            return

        if self._transfer_worker and self._transfer_worker.isRunning():
            return

        # 1a. Validación del panel de verificación (por página + global)
        if self._verification_panel:
            try:
                for i in range(len(self._pages)):
                    ok, msg = self._verification_panel.validate_page(i)
                    if not ok:
                        self._navigate_to(i)
                        QMessageBox.warning(
                            self,
                            self.tr("Validación fallida"),
                            msg,
                        )
                        return
                ok, msg = self._verification_panel.validate()
                if not ok:
                    QMessageBox.warning(
                        self,
                        self.tr("Validación fallida"),
                        msg,
                    )
                    return
            except Exception as e:
                log.error("Error en verification_panel.validate: %s", e)
                QMessageBox.critical(
                    self,
                    self.tr("Error de validación"),
                    self.tr("Error en el script de validación:\n{0}").format(e),
                )
                return

        # 1b. Campos obligatorios y on_transfer_validate (falla cerrado).
        # Los campos del panel se guardan ANTES de validar: el BatchContext
        # que recibe el script se lee de la BD, y antes veía el valor del
        # intento anterior.
        batch_fields = self._metadata_panel.get_batch_fields()
        if self._batch_id:
            with self._session_factory() as session:
                from app.db.repositories.batch_repo import BatchRepository

                batch = BatchRepository(session).get_by_id(self._batch_id)
                if batch:
                    batch.fields_json = json.dumps(batch_fields, ensure_ascii=False)
                    session.commit()
        try:
            fields_def = json.loads(
                self._application.batch_fields_json if self._application else "[]"
            )
        except json.JSONDecodeError, TypeError:
            fields_def = []
        config = parse_transfer_config(
            self._application.transfer_json if self._application else "{}",
        )
        pages_data = []
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            for page in self._pages:
                if page.is_excluded:
                    continue
                db_page = page_repo.get_by_id(page.id)
                if db_page is not None:
                    pages_data.append(transfer_page_dict(db_page))
        reason = validate_before_transfer(
            script_engine=self._script_engine,
            contexts={
                "app": self._build_app_context(),
                "batch": self._build_batch_context(),
            },
            fields_def=fields_def if isinstance(fields_def, list) else [],
            batch_fields=batch_fields,
            pages=pages_data,
            config=config,
        )
        if reason:
            log.warning("Transferencia bloqueada: %s", reason)
            QMessageBox.warning(
                self,
                self.tr("Transferencia cancelada"),
                reason,
            )
            return

        # 2. Confirmación
        reply = QMessageBox.question(
            self,
            self.tr("Confirmar transferencia"),
            self.tr("\u00bfTransferir lote con {0} p\u00e1gina(s)?").format(
                len(self._pages)
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 4. Lanzar worker: transferencia estándar (si está activada) y
        # después on_transfer_advanced (si está definido). Ver transfer_flow.
        script_eng = self._script_engine
        advanced_ctx = {
            "app": self._build_app_context(),
            "batch": self._build_batch_context(),
        }

        self._transfer_worker = TransferWorker(
            transfer_service=self._transfer_service,
            config=config,
            pages=pages_data,
            batch_fields=batch_fields,
            batch_id=self._batch_id,
            script_engine=script_eng,
            advanced_contexts=advanced_ctx,
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
                self,
                self.tr("Transferencia completada"),
                self.tr("Se transfirieron {0} fichero(s)\nDestino: {1}").format(
                    result.files_transferred,
                    result.output_path,
                ),
            )

            # Cerrar después de transferencia (APP-03)
            if self._application and self._application.close_after_transfer:
                self.close()
            else:
                self._start_new_batch_after_export()
        else:
            errors = "\n".join(result.errors[:5])
            QMessageBox.warning(
                self,
                self.tr("Transferencia con errores"),
                self.tr("Ficheros: {0}\nErrores:\n{1}").format(
                    result.files_transferred,
                    errors,
                ),
            )

    def _on_transfer_error(self, error: str) -> None:
        """Error durante la transferencia."""
        self._btn_transfer.setEnabled(True)
        QMessageBox.critical(self, self.tr("Error de transferencia"), error)

    # ==================================================================
    # Cerrar lote sin transferir
    # ==================================================================

    def _start_new_batch_after_export(self) -> None:
        """Cierra el lote exportado y prepara uno nuevo conservando campos de lote."""
        saved_fields = self._metadata_panel.get_batch_fields()

        self._thumbnail_panel.clear()
        self._viewer.clear()
        self._lbl_image_info.clear()
        self._barcode_panel.clear()

        self._create_new_batch()
        self._metadata_panel.set_batch_fields(saved_fields)

        self._call_verification_hook("on_batch_loaded")
        self._fire_event("on_batch_loaded")

        # Persistir los campos en el nuevo lote
        if self._batch_id:
            with self._session_factory() as session:
                from app.db.repositories.batch_repo import BatchRepository

                repo = BatchRepository(session)
                batch = repo.get_by_id(self._batch_id)
                if batch:
                    batch.fields_json = json.dumps(saved_fields, ensure_ascii=False)
                    session.commit()

        self._status_bar.showMessage(self.tr("Nuevo lote creado"), 3000)

    def _on_close_batch(self) -> None:
        """Cierra el lote actual y crea uno nuevo."""
        if self._batch_id is None or not self._pages:
            QMessageBox.information(
                self,
                self.tr("Sin lote"),
                self.tr("No hay un lote activo con p\u00e1ginas."),
            )
            return

        if self._recognition_worker and self._recognition_worker.isRunning():
            QMessageBox.warning(
                self,
                self.tr("Procesando"),
                self.tr(
                    "Espera a que termine el reconocimiento antes de cerrar el lote."
                ),
            )
            return

        reply = QMessageBox.question(
            self,
            self.tr("Cerrar lote"),
            self.tr(
                "\u00bfCerrar el lote {0} sin transferir?\n"
                "Se podr\u00e1 reabrir desde el gestor de lotes."
            ).format(self._batch_id),
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
            self.tr("Lote {0} cerrado").format(self._batch_id),
            3000,
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
            self._current_page_index,
            state,
        )
        self._viewer.set_state(state)

        status = self.tr("excluida") if page.is_excluded else self.tr("incluida")
        self._status_bar.showMessage(self.tr("P\u00e1gina {0}").format(status), 2000)

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
            fields_json=page.index_fields_json,
            is_excluded=page.is_excluded,
        )

    def _on_delete_current_page(self) -> None:
        """Elimina solo la página actual."""
        if self._current_page_index < 0:
            return

        reply = QMessageBox.question(
            self,
            self.tr("Confirmar eliminaci\u00f3n"),
            self.tr("\u00bfEliminar la p\u00e1gina actual?"),
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
                    fields_json=p.index_fields_json,
                    is_excluded=p.is_excluded,
                )
                self._thumbnail_panel.add_thumbnail(i, img, state)

        if self._pages:
            idx = min(self._current_page_index, len(self._pages) - 1)
            self._navigate_to(idx)
        else:
            self._current_page_index = -1
            self._viewer.clear()
            self._lbl_image_info.clear()
        self._update_page_info()

    def _on_delete_from_current(self) -> None:
        """Elimina páginas desde la actual hasta el final."""
        if self._current_page_index < 0:
            return

        count = len(self._pages) - self._current_page_index
        reply = QMessageBox.question(
            self,
            self.tr("Confirmar eliminaci\u00f3n"),
            self.tr("\u00bfEliminar {0} p\u00e1gina(s) desde la actual?").format(count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pages_to_delete = self._pages[self._current_page_index :]
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
                    fields_json=page.index_fields_json,
                    is_excluded=page.is_excluded,
                )
                self._thumbnail_panel.add_thumbnail(i, img, state)

        if self._pages:
            idx = min(self._current_page_index, len(self._pages) - 1)
            self._navigate_to(idx)
        else:
            self._current_page_index = -1
            self._viewer.clear()
            self._lbl_image_info.clear()
        self._update_page_info()

    # ==================================================================
    # Barcode manual
    # ==================================================================

    def _on_insert_barcode(self) -> None:
        """Inserta un barcode manual en la página actual."""
        if self._current_page_index < 0 or self._add_barcode_hidden():
            return

        page = self._pages[self._current_page_index]

        # Leer configuración de barcode manual
        try:
            ai_config = json.loads(self._application.ai_config_json or "{}")
        except json.JSONDecodeError, TypeError:
            ai_config = {}
        bc_regex = ai_config.get("barcode_regex", "")
        bc_fixed = ai_config.get("barcode_fixed_value", "")

        if bc_fixed:
            value = bc_fixed
        else:
            from PySide6.QtWidgets import QInputDialog

            label = self.tr("Introduce el c\u00f3digo de barras:")
            if bc_regex:
                label += self.tr("\n(Formato: {0})").format(bc_regex)
            value, ok = QInputDialog.getText(self, self.tr("Barcode manual"), label)
            if not ok or not value.strip():
                return
            value = value.strip()

            # Validar con regex si está configurada. Acotada en tiempo:
            # esto corre en el hilo de la UI y un patrón patológico
            # congelaría la ventana entera.
            if bc_regex:
                from app.utils import safe_regex

                if not safe_regex.fullmatch(bc_regex, value):
                    QMessageBox.warning(
                        self,
                        self.tr("Formato inv\u00e1lido"),
                        self.tr("El valor '{0}' no cumple el patr\u00f3n:\n{1}").format(
                            value,
                            bc_regex,
                        ),
                    )
                    return

        # Persistir en BD
        with self._session_factory() as session:
            barcode = Barcode(
                page_id=page.id,
                value=value,
                symbology="MANUAL",
                engine="manual",
                step_id="manual",
            )
            session.add(barcode)
            session.commit()
            self._push_barcode_undo({"op": "add", "id": barcode.id})

        # Refrescar la vista
        self._navigate_to(self._current_page_index)
        self._status_bar.showMessage(
            self.tr("Barcode manual a\u00f1adido: {0}").format(value), 3000
        )

    def _on_delete_barcode(self, row: int | None = None) -> None:
        """Elimina un barcode de la página actual (papelera de la fila o Supr).

        Sin confirmación, como en FlexibarNET10: Ctrl+Z lo recupera.
        """
        if self._current_page_index < 0:
            return
        if row is None or row < 0:
            row = self._barcode_panel.selected_row()
        if row < 0:
            self._status_bar.showMessage(
                self.tr("Selecciona un barcode para eliminar"),
                3000,
            )
            return

        page = self._pages[self._current_page_index]
        bc_value = ""
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            db_page = page_repo.get_by_id(page.id)
            barcodes = list(db_page.barcodes) if db_page else []
            if not 0 <= row < len(barcodes):
                return
            target = barcodes[row]
            bc_value = target.value
            self._push_barcode_undo({"op": "delete", "data": _barcode_snapshot(target)})
            session.delete(target)
            session.commit()

        self._navigate_to(self._current_page_index)
        self._status_bar.showMessage(
            self.tr("Barcode eliminado: {0} (Ctrl+Z para deshacer)").format(bc_value),
            5000,
        )

    def _push_barcode_undo(self, entry: dict[str, Any]) -> None:
        """Apila una edición de barcodes para poder deshacerla."""
        entry["page_index"] = self._current_page_index
        self._barcode_undo.append(entry)
        del self._barcode_undo[:-50]

    def _on_undo_barcode(self) -> None:
        """Deshace la última edición de barcodes (Ctrl+Z)."""
        if not self._barcode_undo:
            self._status_bar.showMessage(self.tr("Nada que deshacer"), 2000)
            return
        entry = self._barcode_undo.pop()
        with self._session_factory() as session:
            if entry["op"] == "add":
                added = session.get(Barcode, entry["id"])
                if added is not None:
                    session.delete(added)
            else:
                session.add(Barcode(**entry["data"]))
            session.commit()
        target = entry.get("page_index", self._current_page_index)
        self._navigate_to(target if 0 <= target < len(self._pages) else 0)
        self._status_bar.showMessage(self.tr("Edición de barcodes deshecha"), 3000)

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
                self.tr("Re-procesado completado"),
                3000,
            ),
        )
        self._recognition_worker.cancelled.connect(
            lambda procesadas, totales: self._status_bar.showMessage(
                self.tr("Re-procesado cancelado"),
                5000,
            ),
        )
        self._recognition_worker.start()
        self._recognition_worker.enqueue_page(
            self._current_page_index,
            image,
            separator_state(page),
        )
        self._recognition_worker.signal_no_more_pages()
        self._status_bar.showMessage(self.tr("Re-procesando p\u00e1gina..."))

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

    def _build_page_context(self, page_index: int) -> PageContext:
        """Construye un PageContext ligero para scripts lifecycle.

        Lee la página por ``page_index`` desde la BD del batch actual,
        materializa los barcodes y los campos de indexación. Si no hay
        batch o la página no existe, devuelve un ``PageContext`` con
        ``id=0`` y campos vacíos para que los scripts no fallen al
        acceder a atributos básicos.
        """
        from app.pipeline.page_context import BarcodeResult, PageFlags

        if not self._batch_id:
            return PageContext(page_index=page_index)
        try:
            with self._session_factory() as session:
                page_repo = PageRepository(session)
                page = page_repo.get_by_batch_and_index(self._batch_id, page_index)
                if page is None:
                    return PageContext(page_index=page_index)
                try:
                    fields = json.loads(page.index_fields_json or "{}")
                except json.JSONDecodeError, TypeError:
                    fields = {}
                barcodes = [
                    BarcodeResult(
                        value=b.value,
                        symbology=b.symbology or "",
                        engine=b.engine or "",
                        step_id=b.step_id or "",
                        quality=b.quality or 0.0,
                        pos_x=b.pos_x or 0,
                        pos_y=b.pos_y or 0,
                        pos_w=b.pos_w or 0,
                        pos_h=b.pos_h or 0,
                        role=b.role or "",
                    )
                    for b in page.barcodes
                ]
                return PageContext(
                    id=page.id,
                    page_index=page.page_index,
                    barcodes=barcodes,
                    ocr_text=page.ocr_text or "",
                    fields=fields,
                    flags=PageFlags(
                        needs_review=page.needs_review,
                        review_reason=page.review_reason or "",
                    ),
                )
        except Exception:
            return PageContext(page_index=page_index)

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
        if self._script_engine is None:
            return None
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
        """Actualiza los contadores del lote en la barra de estado."""
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
                    separators += sum(1 for b in p.barcodes if b.role == "separator")

        self._lbl_counters.setText(
            format_lot_counters(
                {
                    "total_pages": stats.get("total_pages", 0),
                    "with_barcode": pages_with_bc,
                    "separators": separators,
                    "needs_review": stats.get("needs_review", 0),
                },
                self.tr,
            )
        )

    def _save_source_settings(self) -> None:
        """Persiste el estado del origen de documentos para esta app."""
        s = QSettings("DocScanStudio", "Workbench")
        prefix = f"source/{self._app_id}"
        s.setValue(f"{prefix}/scanner_name", self._combo_source.currentText())
        s.setValue(
            f"{prefix}/source_type", self._combo_source_type.currentData() or "flatbed"
        )
        s.setValue(f"{prefix}/show_config", self._chk_scanner_config.isChecked())
        # Opciones del escáner (resolution, mode, etc.)
        if self._last_scan_options:
            s.setValue(f"{prefix}/scan_options", json.dumps(self._last_scan_options))

    def _restore_source_settings(self) -> None:
        """Restaura el estado del origen de documentos para esta app."""
        s = QSettings("DocScanStudio", "Workbench")
        prefix = f"source/{self._app_id}"
        scanner_name = s.value(f"{prefix}/scanner_name", "")
        source_type = s.value(f"{prefix}/source_type", "flatbed")
        show_config = s.value(f"{prefix}/show_config", False)
        scan_options_json = s.value(f"{prefix}/scan_options", "")

        # Convertir string "true"/"false" de QSettings a bool
        if isinstance(show_config, str):
            show_config = show_config.lower() == "true"

        # Restaurar opciones del escáner
        if scan_options_json:
            try:
                self._last_scan_options = json.loads(scan_options_json)
            except json.JSONDecodeError, TypeError:
                self._last_scan_options = {}

        # Sin enumerar: el escáner de la sesión anterior queda elegido y la
        # lista completa se pide al abrir ⚙ (en SANE tarda varios segundos).
        self._scan_popup.preselect_scanner(scanner_name)

        # Restaurar tipo de fuente (flatbed/ADF)
        type_idx = self._combo_source_type.findData(source_type)
        if type_idx >= 0:
            self._combo_source_type.setCurrentIndex(type_idx)

        self._chk_scanner_config.setChecked(bool(show_config))
        self._update_scanner_chip()

    # ==================================================================
    # Teclado (UI-12)
    # ==================================================================

    def keyPressEvent(self, event) -> None:
        """Despacha on_key_event si hay combinación Ctrl/Alt/Shift."""
        mods = event.modifiers()
        has_mod = bool(
            mods
            & (
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
    # Drag & drop
    # ==================================================================

    _IMPORT_SUFFIXES = {
        ".pdf",
        ".tiff",
        ".tif",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
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
                worker.wait(500)

        self._save_source_settings()
        self._fire_event("on_app_end")
        self._metadata_panel.cleanup()
        if self._scanner is not None:
            try:
                self._scanner.close()
            except Exception:
                pass
            self._scanner = None

        # Cleanup panel de verificación
        self._call_verification_hook("cleanup")
        self._verification_panel = None

        # Liberar referencias pesadas para que el GC pueda actuar
        self._pages.clear()
        self._scan_worker = None
        self._recognition_worker = None
        self._transfer_worker = None
        self._script_engine = None
        self._transfer_service = None

        self.closed.emit()
        super().closeEvent(event)
        self.deleteLater()
