"""Diálogo de edición de paso Barcode."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from app.pipeline.steps import BarcodeStep

ALL_SYMBOLOGIES = [
    "Code128", "Code39", "Code93", "EAN13", "EAN8",
    "UPCA", "UPCE", "ITF", "Codabar",
    "QR", "DataMatrix", "PDF417", "Aztec", "MicroQR",
]

ALL_ORIENTATIONS = ["horizontal", "vertical", "diagonal"]


class BarcodeStepDialog(QDialog):
    """Editor de paso de lectura de barcodes."""

    def __init__(
        self, step: BarcodeStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle("Lectura de barcodes")
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["motor1", "motor2"])
        self._engine_combo.setCurrentText(step.engine)
        layout.addRow("Motor:", self._engine_combo)

        self._symb_edit = QLineEdit(", ".join(step.symbologies))
        self._symb_edit.setPlaceholderText(
            "Code128, QR, DataMatrix (vacío = todas)"
        )
        layout.addRow("Simbologías:", self._symb_edit)

        self._regex_edit = QLineEdit(step.regex)
        self._regex_edit.setPlaceholderText("Filtro regex (vacío = sin filtro)")
        layout.addRow("Regex:", self._regex_edit)

        self._regex_symb = QCheckBox("Incluir simbología en regex")
        self._regex_symb.setChecked(step.regex_include_symbology)
        layout.addRow("", self._regex_symb)

        self._orient_edit = QLineEdit(", ".join(step.orientations))
        self._orient_edit.setPlaceholderText("horizontal, vertical, diagonal")
        layout.addRow("Orientaciones:", self._orient_edit)

        self._quality = QDoubleSpinBox()
        self._quality.setRange(0.0, 1.0)
        self._quality.setSingleStep(0.1)
        self._quality.setValue(step.quality_threshold)
        layout.addRow("Umbral calidad:", self._quality)

        self._window_edit = QLineEdit()
        if step.window:
            self._window_edit.setText(
                ", ".join(str(v) for v in step.window)
            )
        self._window_edit.setPlaceholderText("x, y, w, h (vacío = completa)")
        layout.addRow("Ventana:", self._window_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> BarcodeStep:
        self._step.engine = self._engine_combo.currentText()
        self._step.symbologies = [
            s.strip() for s in self._symb_edit.text().split(",") if s.strip()
        ]
        self._step.regex = self._regex_edit.text().strip()
        self._step.regex_include_symbology = self._regex_symb.isChecked()
        self._step.orientations = [
            s.strip() for s in self._orient_edit.text().split(",") if s.strip()
        ]
        self._step.quality_threshold = self._quality.value()

        window_text = self._window_edit.text().strip()
        if window_text:
            parts = [int(p.strip()) for p in window_text.split(",")]
            self._step.window = tuple(parts) if len(parts) == 4 else None
        else:
            self._step.window = None

        return self._step
