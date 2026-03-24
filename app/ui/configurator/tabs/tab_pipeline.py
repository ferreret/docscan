"""Pestaña Pipeline del configurador — editor de lista de pasos.

Permite añadir, editar, eliminar, reordenar y habilitar/deshabilitar
pasos del pipeline de procesado.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Qt, QSize
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
    elif isinstance(step, OcrStep):
        langs = ", ".join(step.languages)
        detail = f"{step.engine} [{langs}]"
    elif isinstance(step, ScriptStep):
        detail = step.label or step.entry_point or _tr("(sin nombre)")
    else:
        detail = step.id

    enabled = "✓" if step.enabled else "✗"
    return f"[{enabled}] {prefix}: {detail}"


class PipelineTab(QWidget):
    """Editor de lista de pasos del pipeline."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._steps: list[PipelineStep] = []
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
        for type_key, label in STEP_TYPE_LABELS().items():
            self._type_combo.addItem(label, type_key)
        actions_layout.addWidget(self._type_combo)

        self._btn_add = QPushButton(self.tr("Añadir"))
        self._btn_add.setProperty("cssClass", "primary")
        self._btn_edit = QPushButton(self.tr("Editar"))
        self._btn_delete = QPushButton(self.tr("Eliminar"))
        self._btn_delete.setProperty("cssClass", "danger")
        self._btn_toggle = QPushButton(self.tr("On/Off"))
        self._btn_up = QPushButton("↑")
        self._btn_down = QPushButton("↓")

        for btn in (
            self._btn_add, self._btn_edit, self._btn_delete,
            self._btn_toggle, self._btn_up, self._btn_down,
        ):
            actions_layout.addWidget(btn)

        layout.addWidget(actions_bar)

        # Lista de pasos
        self._list = QListWidget()
        self._list.setObjectName("pipelineStepList")
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        layout.addWidget(self._list)

        # Conexiones
        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_toggle.clicked.connect(self._on_toggle)
        self._btn_up.clicked.connect(self._on_move_up)
        self._btn_down.clicked.connect(self._on_move_down)
        self._list.itemDoubleClicked.connect(self._on_edit)

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
        self._list.clear()
        for step in self._steps:
            item = QListWidgetItem(_step_display_text(step))
            item.setSizeHint(QSize(0, 38))
            self._list.addItem(item)

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
            self._steps[idx], self._steps[idx - 1]
        )
        self._refresh_list()
        self._list.setCurrentRow(idx - 1)

    def _on_move_down(self) -> None:
        idx = self._selected_index()
        if idx is None or idx >= len(self._steps) - 1:
            return
        self._steps[idx], self._steps[idx + 1] = (
            self._steps[idx + 1], self._steps[idx]
        )
        self._refresh_list()
        self._list.setCurrentRow(idx + 1)

    # ------------------------------------------------------------------
    # Diálogos de paso
    # ------------------------------------------------------------------

    def _create_step_dialog(self, step: PipelineStep) -> Any:
        """Crea el diálogo de edición apropiado para el tipo de paso."""
        from app.ui.configurator.step_dialogs.image_op_dialog import ImageOpDialog
        from app.ui.configurator.step_dialogs.barcode_step_dialog import BarcodeStepDialog
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
