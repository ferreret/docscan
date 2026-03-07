"""Diálogo de edición de paso Script."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.steps import ScriptStep


class ScriptStepDialog(QDialog):
    """Editor de paso de script Python."""

    def __init__(
        self, step: ScriptStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
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

        layout.addWidget(QLabel("Código:"))

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

    def get_step(self) -> ScriptStep:
        self._step.label = self._label_edit.text().strip()
        self._step.entry_point = self._entry_edit.text().strip()
        self._step.script = self._code_edit.toPlainText()
        return self._step
