"""Pestaña Pipeline del configurador — editor de lista de pasos.

Permite añadir, editar, eliminar, reordenar y habilitar/deshabilitar
pasos del pipeline de procesado.

Cada fila lleva, como en FlexibarNET 10, una casilla real de activo, el
icono del tipo de paso y su nombre. El icono y su color distinguen el tipo
de un vistazo; un paso desactivado se ve atenuado.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QModelIndex, QT_TRANSLATE_NOOP, Qt, QSize
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.pipeline.serializer import serialize, deserialize
from app.ui.icons import icon
from app.ui.palette import color
from app.pipeline.steps import (
    STEP_TYPE_MAP,
    BarcodeStep,
    ImageOpStep,
    OcrStep,
    PipelineStep,
    ScriptStep,
)

log = logging.getLogger(__name__)

# Etiquetas por tipo de paso (marcadas para lupdate, traducidas en uso)
_STEP_TYPE_LABELS_SRC = {
    "image_op": QT_TRANSLATE_NOOP("PipelineTab", "Imagen"),
    "barcode": QT_TRANSLATE_NOOP("PipelineTab", "Barcode"),
    "ocr": QT_TRANSLATE_NOOP("PipelineTab", "OCR"),
    "script": QT_TRANSLATE_NOOP("PipelineTab", "Script"),
}

_tr = lambda s: QCoreApplication.translate("PipelineTab", s)

# Icono Lucide y color de la paleta de cada tipo de paso
STEP_TYPE_ICONS: dict[str, tuple[str, str]] = {
    "image_op": ("image", "mauve"),
    "barcode": ("barcode", "blue"),
    "ocr": ("scan-text", "green"),
    "script": ("code", "peach"),
}

# El item guarda su paso: al arrastrar, el orden de _steps sale de la lista.
STEP_ROLE = Qt.ItemDataRole.UserRole


def STEP_TYPE_LABELS() -> dict[str, str]:
    """Devuelve etiquetas de tipo de paso traducidas."""
    return {k: _tr(v) for k, v in _STEP_TYPE_LABELS_SRC.items()}


def _step_display_text(step: PipelineStep) -> str:
    """Genera el texto de visualización de un paso."""
    labels = STEP_TYPE_LABELS()
    prefix = labels.get(step.type, step.type)

    if isinstance(step, ImageOpStep):
        detail = step.op or _tr("(sin operación)")
    elif isinstance(step, BarcodeStep):
        symb = ", ".join(step.symbologies[:3]) or _tr("todas")
        detail = f"{step.engine} · {symb}"
        if step.separator_enabled:
            condition = {
                "regex": step.separator_regex,
                "symbology": step.separator_symbology,
                "fixed_value": step.separator_fixed_value,
            }.get(step.separator_by, "")
            detail += " · " + _tr("separador") + (f" {condition}" if condition else "")
    elif isinstance(step, OcrStep):
        langs = ", ".join(step.languages)
        detail = f"{step.engine} [{langs}]"
    elif isinstance(step, ScriptStep):
        detail = step.label or step.entry_point or _tr("(sin nombre)")
    else:
        detail = step.id

    return f"{prefix}: {detail}"


class PipelineTab(QWidget):
    """Editor de lista de pasos del pipeline."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._steps: list[PipelineStep] = []
        self._test_worker = None
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Barra de acciones
        actions_bar = QWidget()
        actions_bar.setObjectName("pipelineToolbar")
        actions_layout = QHBoxLayout(actions_bar)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(6)

        self._type_combo = QComboBox()
        self._type_combo.setToolTip(self.tr("Tipo de paso a añadir al pipeline"))
        for type_key, label in STEP_TYPE_LABELS().items():
            self._type_combo.addItem(label, type_key)
        actions_layout.addWidget(self._type_combo)

        self._btn_add = QPushButton(self.tr("Añadir"))
        self._btn_add.setProperty("cssClass", "primary")
        self._btn_add.setToolTip(self.tr("Añadir un nuevo paso del tipo seleccionado"))
        self._btn_edit = QPushButton(self.tr("Editar"))
        self._btn_edit.setToolTip(
            self.tr("Editar la configuración del paso seleccionado")
        )
        self._btn_delete = QPushButton(self.tr("Eliminar"))
        self._btn_delete.setProperty("cssClass", "danger")
        self._btn_delete.setToolTip(
            self.tr("Eliminar el paso seleccionado del pipeline")
        )
        self._btn_up = QPushButton()
        self._btn_up.setToolTip(
            self.tr("Mover el paso hacia arriba en el orden de ejecución")
        )
        self._btn_down = QPushButton()
        self._btn_down.setToolTip(
            self.tr("Mover el paso hacia abajo en el orden de ejecución")
        )
        self._btn_test = QPushButton(self.tr("Probar pipeline"))
        self._btn_test.setProperty("cssClass", "accent")
        self._btn_test.setToolTip(
            self.tr(
                "Ejecutar el pipeline sobre una imagen de muestra para verificar el resultado"
            )
        )

        for btn in (
            self._btn_add,
            self._btn_edit,
            self._btn_delete,
            self._btn_up,
            self._btn_down,
        ):
            actions_layout.addWidget(btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self._btn_test)

        layout.addWidget(actions_bar)

        # Lista de pasos
        self._list = QListWidget()
        self._list.setObjectName("pipelineStepList")
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setIconSize(QSize(18, 18))
        self._list.setToolTip(
            self.tr(
                "Lista de pasos del pipeline. La casilla activa o desactiva el paso; "
                "doble clic para editar, arrastrar para reordenar"
            )
        )
        layout.addWidget(self._list)
        self._refresh_icons()

        # Conexiones
        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_up.clicked.connect(self._on_move_up)
        self._btn_down.clicked.connect(self._on_move_down)
        self._btn_test.clicked.connect(self._on_test_pipeline)
        self._list.itemDoubleClicked.connect(self._on_edit)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)

    def _load_from_app(self, app: Application) -> None:
        """Carga los pasos desde el JSON de la aplicación."""
        try:
            self._steps = deserialize(app.pipeline_json)
        except Exception as e:
            log.error("Error al deserializar pipeline: %s", e)
            self._steps = []
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresca la lista visual."""
        self._list.blockSignals(True)
        self._list.clear()
        for step in self._steps:
            item = QListWidgetItem(_step_display_text(step))
            item.setData(STEP_ROLE, step)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setSizeHint(QSize(0, 38))
            self._style_item(item, step)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _style_item(self, item: QListWidgetItem, step: PipelineStep) -> None:
        """Casilla, icono del tipo y color según el paso esté activo o no."""
        item.setCheckState(
            Qt.CheckState.Checked if step.enabled else Qt.CheckState.Unchecked
        )
        icon_name, role = STEP_TYPE_ICONS.get(step.type, ("circle", "text"))
        item.setIcon(icon(icon_name, role if step.enabled else "text_disabled", 18))
        item.setForeground(
            QBrush(QColor(color("text") if step.enabled else color("text_disabled")))
        )
        item.setToolTip(
            "" if step.enabled else self.tr("Paso desactivado: no se ejecuta")
        )

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """La casilla activa o desactiva el paso."""
        step = item.data(STEP_ROLE)
        if step is None:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        if step.enabled == enabled:
            return
        step.enabled = enabled
        self._list.blockSignals(True)
        self._style_item(item, step)
        self._list.blockSignals(False)

    def _on_rows_moved(self, *_args: QModelIndex | int) -> None:
        """Tras arrastrar, el orden de los pasos es el de la lista."""
        self._steps = [
            self._list.item(i).data(STEP_ROLE) for i in range(self._list.count())
        ]

    def _refresh_icons(self) -> None:
        """Iconos de los botones de mover (y de los pasos) con el tema activo."""
        self._btn_up.setIcon(icon("chevron-up", "text", 16))
        self._btn_down.setIcon(icon("chevron-down", "text", 16))
        for i in range(self._list.count()):
            item = self._list.item(i)
            self._list.blockSignals(True)
            self._style_item(item, item.data(STEP_ROLE))
            self._list.blockSignals(False)

    def _selected_index(self) -> int | None:
        row = self._list.currentRow()
        return row if row >= 0 else None

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        """Añade un paso nuevo del tipo seleccionado."""
        type_key = self._type_combo.currentData()
        step_cls = STEP_TYPE_MAP[type_key]
        step_id = f"step_{uuid.uuid4().hex[:8]}"
        step = step_cls(id=step_id)

        # Abrir diálogo de edición
        dialog = self._create_step_dialog(step)
        if dialog and dialog.exec():
            step = dialog.get_step()
            self._steps.append(step)
            self._refresh_list()
            self._list.setCurrentRow(len(self._steps) - 1)

    def _on_edit(self) -> None:
        """Edita el paso seleccionado."""
        idx = self._selected_index()
        if idx is None:
            return

        step = self._steps[idx]
        dialog = self._create_step_dialog(step)
        if dialog and dialog.exec():
            self._steps[idx] = dialog.get_step()
            self._refresh_list()
            self._list.setCurrentRow(idx)

    def _on_delete(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        self._steps.pop(idx)
        self._refresh_list()

    def _on_toggle(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        self._steps[idx].enabled = not self._steps[idx].enabled
        self._refresh_list()
        self._list.setCurrentRow(idx)

    def _on_move_up(self) -> None:
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        self._steps[idx - 1], self._steps[idx] = (
            self._steps[idx],
            self._steps[idx - 1],
        )
        self._refresh_list()
        self._list.setCurrentRow(idx - 1)

    def _on_move_down(self) -> None:
        idx = self._selected_index()
        if idx is None or idx >= len(self._steps) - 1:
            return
        self._steps[idx], self._steps[idx + 1] = (
            self._steps[idx + 1],
            self._steps[idx],
        )
        self._refresh_list()
        self._list.setCurrentRow(idx + 1)

    # ------------------------------------------------------------------
    # Diálogos de paso
    # ------------------------------------------------------------------

    def _create_step_dialog(self, step: PipelineStep) -> Any:
        """Crea el diálogo de edición apropiado para el tipo de paso."""
        from app.ui.configurator.step_dialogs.image_op_dialog import ImageOpDialog
        from app.ui.configurator.step_dialogs.barcode_step_dialog import (
            BarcodeStepDialog,
        )
        from app.ui.configurator.step_dialogs.ocr_step_dialog import OcrStepDialog
        from app.ui.configurator.step_dialogs.script_step_dialog import ScriptStepDialog

        dialogs = {
            "image_op": ImageOpDialog,
            "barcode": BarcodeStepDialog,
            "ocr": OcrStepDialog,
            "script": ScriptStepDialog,
        }
        dialog_cls = dialogs.get(step.type)
        if dialog_cls:
            return dialog_cls(step, parent=self)
        return None

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def apply_to(self, app: Application) -> None:
        """Serializa los pasos al JSON de la aplicación."""
        app.pipeline_json = serialize(self._steps)

    def get_steps(self) -> list[PipelineStep]:
        """Devuelve los pasos actuales (para testing)."""
        return list(self._steps)

    # ------------------------------------------------------------------
    # Probar pipeline
    # ------------------------------------------------------------------

    def _on_test_pipeline(self) -> None:
        """Ejecuta el pipeline sobre una imagen de muestra."""
        if not self._steps:
            QMessageBox.information(
                self,
                self.tr("Pipeline vacio"),
                self.tr("Añade al menos un paso antes de probar."),
            )
            return

        from PySide6.QtWidgets import QFileDialog, QProgressDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Seleccionar imagen de prueba"),
            "",
            self.tr("Imagenes (*.tif *.tiff *.png *.jpg *.jpeg *.bmp *.pdf)"),
        )
        if not path:
            return

        from app.services.image_lib import ImageLib

        try:
            images = ImageLib.load(path)
            if not images:
                QMessageBox.warning(
                    self,
                    self.tr("Error"),
                    self.tr("No se pudo cargar la imagen."),
                )
                return
            image = images[0]
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Error al cargar"),
                str(e),
            )
            return

        # Preparar servicios y executor
        from app.pipeline.test_executor import InstrumentedPipelineExecutor
        from app.services.image_pipeline import ImagePipelineService
        from app.services.script_engine import ScriptEngine

        image_service = ImagePipelineService()
        script_engine = ScriptEngine()

        # Compilar scripts
        for step in self._steps:
            if isinstance(step, ScriptStep):
                script_engine.compile_step(step)

        # Intentar cargar servicios opcionales
        barcode_service = None
        ocr_service = None
        try:
            from app.services.barcode_service import BarcodeService

            barcode_service = BarcodeService()
        except Exception:
            log.debug("BarcodeService no disponible para test pipeline")
        try:
            from app.services.ocr_service import OcrService

            ocr_service = OcrService()
        except Exception:
            log.debug("OcrService no disponible para test pipeline")

        executor = InstrumentedPipelineExecutor(
            steps=self._steps,
            image_service=image_service,
            script_engine=script_engine,
            barcode_service=barcode_service,
            ocr_service=ocr_service,
        )

        # Contextos dummy
        from app.workers.recognition_worker import AppContext, BatchContext

        app_ctx = AppContext(
            name=self._app.name if self._app else "Test",
            description=self._app.description if self._app else "",
        )
        batch_ctx = BatchContext()

        # Progress dialog
        progress = QProgressDialog(
            self.tr("Ejecutando pipeline..."),
            None,
            0,
            0,
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        # Worker
        from pathlib import Path
        from app.workers.test_pipeline_worker import TestPipelineWorker

        source_name = Path(path).name
        self._test_worker = TestPipelineWorker(
            executor=executor,
            image=image,
            app_context=app_ctx,
            batch_context=batch_ctx,
            parent=self,
        )
        self._test_worker.finished.connect(
            lambda page, snaps: self._on_test_finished(
                page,
                snaps,
                progress,
                image,
                source_name,
            )
        )
        self._test_worker.error_occurred.connect(
            lambda msg: self._on_test_error(msg, progress)
        )
        self._test_worker.start()

    def _on_test_finished(
        self,
        page: Any,
        snapshots: list,
        progress: Any,
        original_image: Any,
        source_name: str,
    ) -> None:
        """Muestra el dialogo de resultados."""
        progress.close()
        from app.ui.configurator.test_pipeline_dialog import (
            TestPipelineResultDialog,
        )

        dialog = TestPipelineResultDialog(
            snapshots=snapshots,
            original_image=original_image,
            source_name=source_name,
            parent=self,
        )
        dialog.exec()

    def _on_test_error(self, error_msg: str, progress: Any) -> None:
        progress.close()
        QMessageBox.critical(
            self,
            self.tr("Error en pipeline"),
            error_msg,
        )
