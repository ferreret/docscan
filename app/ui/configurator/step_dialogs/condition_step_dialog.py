"""Diálogo de edición de paso Condition."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from app.pipeline.steps import ConditionStep


class ConditionStepDialog(QDialog):
    """Editor de paso de condición."""

    def __init__(
        self, step: ConditionStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle("Condición")
        self.setMinimumWidth(500)

        layout = QFormLayout(self)

        self._label_edit = QLineEdit(step.label)
        self._label_edit.setPlaceholderText("Nombre descriptivo")
        layout.addRow("Etiqueta:", self._label_edit)

        self._expr_edit = QLineEdit(step.expression)
        self._expr_edit.setPlaceholderText(
            'len(page.barcodes) > 0'
        )
        layout.addRow("Expresión:", self._expr_edit)

        self._on_false_edit = QLineEdit(step.on_false)
        self._on_false_edit.setPlaceholderText(
            "skip_step:step_id | skip_to:step_id | abort"
        )
        layout.addRow("Si falso:", self._on_false_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> ConditionStep:
        self._step.label = self._label_edit.text().strip()
        self._step.expression = self._expr_edit.text().strip()
        self._step.on_false = self._on_false_edit.text().strip()
        return self._step
