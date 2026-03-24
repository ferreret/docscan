"""Diálogo de edición de paso OCR."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from app.pipeline.steps import OcrStep


class OcrStepDialog(QDialog):
    """Editor de paso OCR."""

    def __init__(
        self, step: OcrStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle(self.tr("OCR"))
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["rapidocr", "easyocr", "tesseract"])
        self._engine_combo.setCurrentText(step.engine)
        layout.addRow(self.tr("Motor:"), self._engine_combo)

        self._langs_edit = QLineEdit(", ".join(step.languages))
        self._langs_edit.setPlaceholderText("es, en, fr")
        layout.addRow(self.tr("Idiomas:"), self._langs_edit)

        self._full_page = QCheckBox(self.tr("Página completa"))
        self._full_page.setChecked(step.full_page)
        layout.addRow("", self._full_page)

        self._window_edit = QLineEdit()
        if step.window:
            self._window_edit.setText(
                ", ".join(str(v) for v in step.window)
            )
        self._window_edit.setPlaceholderText(self.tr("x, y, w, h (vacío = completa)"))
        layout.addRow(self.tr("Ventana:"), self._window_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> OcrStep:
        self._step.engine = self._engine_combo.currentText()
        self._step.languages = [
            s.strip() for s in self._langs_edit.text().split(",") if s.strip()
        ]
        self._step.full_page = self._full_page.isChecked()

        window_text = self._window_edit.text().strip()
        if window_text:
            parts = [int(p.strip()) for p in window_text.split(",")]
            self._step.window = tuple(parts) if len(parts) == 4 else None
        else:
            self._step.window = None

        return self._step
