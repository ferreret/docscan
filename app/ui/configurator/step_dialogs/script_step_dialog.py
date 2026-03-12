"""Diálogo de edición de paso Script."""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
        self.setWindowTitle("Script Python")
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._label_edit = QLineEdit(step.label)
        self._label_edit.setPlaceholderText("Nombre descriptivo del script")
        form.addRow("Etiqueta:", self._label_edit)

        self._entry_edit = QLineEdit(step.entry_point)
        self._entry_edit.setPlaceholderText("nombre_de_la_funcion")
        form.addRow("Entry point:", self._entry_edit)
        layout.addLayout(form)

        # Barra de código con botón VS Code
        code_bar = QHBoxLayout()
        code_bar.addWidget(QLabel("Código:"))
        code_bar.addStretch()

        self._btn_vscode = QPushButton("Abrir en VS Code")
        self._btn_vscode.setVisible(detect_editor() is not None)
        self._btn_vscode.clicked.connect(self._open_in_vscode)
        code_bar.addWidget(self._btn_vscode)
        layout.addLayout(code_bar)

        self._code_edit = QPlainTextEdit()
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._code_edit.setFont(font)
        self._code_edit.setPlainText(step.script)
        self._code_edit.setTabStopDistance(
            self._code_edit.fontMetrics().horizontalAdvance(" ") * 4
        )
        layout.addWidget(self._code_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_in_vscode(self) -> None:
        """Lanza VS Code para editar el script en hilo separado."""
        self._btn_vscode.setEnabled(False)
        self._btn_vscode.setText("Editando en VS Code...")
        self._editor_worker = _EditorWorker(
            self._code_edit.toPlainText(), "pipeline",
        )
        self._editor_worker.finished.connect(self._on_editor_done)
        self._editor_worker.start()

    def _on_editor_done(self, result: str | None) -> None:
        """Actualiza el código al volver de VS Code."""
        self._btn_vscode.setEnabled(True)
        self._btn_vscode.setText("Abrir en VS Code")
        if result is not None:
            self._code_edit.setPlainText(result)

    def get_step(self) -> ScriptStep:
        self._step.label = self._label_edit.text().strip()
        self._step.entry_point = self._entry_edit.text().strip()
        self._step.script = self._code_edit.toPlainText()
        return self._step
