"""Diálogo de edición de paso Script."""

from __future__ import annotations

import logging

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.steps import ScriptStep
from app.services.external_editor_service import detect_editor, edit_script

log = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = '''\
def process(app, batch, page, pipeline):
    """Procesa cada página del pipeline.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        page: PageContext (image, barcodes, ocr_text, fields, flags)
        pipeline: PipelineContext (skip_step, abort, repeat_step, metadata)
    """
    pass
'''

_HELP_TEXT = QT_TRANSLATE_NOOP(
    "ScriptStepDialog",
    "Variables disponibles: app, batch, page, pipeline, "
    "log, http, re, json, datetime, Path",
)


class _EditorWorker(QThread):
    """Hilo para edición bloqueante en VS Code."""

    finished = Signal(object)  # str | None

    def __init__(self, code: str, context_type: str, event_name: str = "") -> None:
        super().__init__()
        self._code = code
        self._context_type = context_type
        self._event_name = event_name

    def run(self) -> None:
        result = edit_script(self._code, self._context_type, self._event_name)
        self.finished.emit(result)


class ScriptStepDialog(QDialog):
    """Editor de paso de script Python."""

    def __init__(
        self, step: ScriptStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self._editor_worker: _EditorWorker | None = None
        self.setWindowTitle(self.tr("Paso Script Python"))
        self.setMinimumSize(650, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Grupo de configuración ---
        config_group = QGroupBox(self.tr("Configuración"))
        config_form = QFormLayout(config_group)
        config_form.setSpacing(8)

        self._label_edit = QLineEdit(step.label)
        self._label_edit.setPlaceholderText(self.tr("Ej: Asignar roles barcode"))
        config_form.addRow(self.tr("Nombre:"), self._label_edit)

        entry_row = QHBoxLayout()
        self._entry_edit = QLineEdit(step.entry_point or "process")
        self._entry_edit.setPlaceholderText("process")
        self._entry_edit.setMaximumWidth(250)
        entry_row.addWidget(self._entry_edit)
        entry_hint = QLabel(self.tr("Nombre de la función a ejecutar"))
        entry_hint.setProperty("cssClass", "subtitle")
        entry_row.addWidget(entry_hint)
        entry_row.addStretch()
        config_form.addRow(self.tr("Función:"), entry_row)

        layout.addWidget(config_group)

        # --- Grupo de código ---
        code_group = QGroupBox(self.tr("Código Python"))
        code_layout = QVBoxLayout(code_group)
        code_layout.setSpacing(6)

        # Barra superior: ayuda + botón VS Code
        code_bar = QHBoxLayout()
        help_label = QLabel(
            QCoreApplication.translate("ScriptStepDialog", _HELP_TEXT)
        )
        help_label.setProperty("cssClass", "info")
        code_bar.addWidget(help_label, 1)

        self._btn_vscode = QPushButton(self.tr("Abrir en VS Code"))
        self._btn_vscode.setVisible(detect_editor() is not None)
        self._btn_vscode.clicked.connect(self._open_in_vscode)
        code_bar.addWidget(self._btn_vscode)
        code_layout.addLayout(code_bar)

        # Editor de código
        self._code_edit = QPlainTextEdit()
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._code_edit.setFont(font)
        self._code_edit.setTabStopDistance(
            self._code_edit.fontMetrics().horizontalAdvance(" ") * 4
        )

        # Plantilla por defecto si el script está vacío
        code = step.script if step.script and step.script.strip() else _DEFAULT_TEMPLATE
        self._code_edit.setPlainText(code)

        code_layout.addWidget(self._code_edit)
        layout.addWidget(code_group, 1)  # stretch=1 para que ocupe el espacio

        # --- Botones ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Aceptar"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_in_vscode(self) -> None:
        """Lanza VS Code para editar el script en hilo separado."""
        self._btn_vscode.setEnabled(False)
        self._btn_vscode.setText(self.tr("Editando en VS Code..."))
        self._editor_worker = _EditorWorker(
            self._code_edit.toPlainText(), "pipeline",
        )
        self._editor_worker.finished.connect(self._on_editor_done)
        self._editor_worker.start()

    def _on_editor_done(self, result: str | None) -> None:
        """Actualiza el código al volver de VS Code."""
        self._btn_vscode.setEnabled(True)
        self._btn_vscode.setText(self.tr("Abrir en VS Code"))
        if result is not None:
            self._code_edit.setPlainText(result)

    def get_step(self) -> ScriptStep:
        self._step.label = self._label_edit.text().strip()
        self._step.entry_point = self._entry_edit.text().strip() or "process"
        self._step.script = self._code_edit.toPlainText()
        return self._step
