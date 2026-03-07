"""Diálogo de edición de paso IA."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from app.pipeline.steps import AiStep


class AiStepDialog(QDialog):
    """Editor de paso de extracción/clasificación por IA."""

    def __init__(
        self, step: AiStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle("Extracción IA")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["anthropic", "openai", "local_ocr"])
        self._provider_combo.setCurrentText(step.provider)
        layout.addRow("Proveedor:", self._provider_combo)

        self._template_spin = QSpinBox()
        self._template_spin.setRange(0, 9999)
        self._template_spin.setSpecialValueText("(ninguna)")
        self._template_spin.setValue(step.template_id or 0)
        layout.addRow("ID Plantilla:", self._template_spin)

        self._fallback_edit = QLineEdit(step.fallback_provider or "")
        self._fallback_edit.setPlaceholderText("Proveedor alternativo (vacío = ninguno)")
        layout.addRow("Fallback:", self._fallback_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> AiStep:
        self._step.provider = self._provider_combo.currentText()
        val = self._template_spin.value()
        self._step.template_id = val if val > 0 else None
        fb = self._fallback_edit.text().strip()
        self._step.fallback_provider = fb if fb else None
        return self._step
