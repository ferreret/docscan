"""Diálogo de edición de paso Barcode."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QWidget,
)

from app.pipeline.steps import BarcodeStep
from app.utils.symbology_numbers import legend

# (clave guardada, etiqueta) del modo de detección de separador
SEPARATOR_MODES = [
    ("regex", "Expresión regular"),
    ("symbology", "Simbología"),
    ("fixed_value", "Valor fijo"),
]

ALL_SYMBOLOGIES = [
    "Code128",
    "Code39",
    "Code93",
    "EAN13",
    "EAN8",
    "UPCA",
    "UPCE",
    "ITF",
    "Codabar",
    "QR",
    "DataMatrix",
    "PDF417",
    "Aztec",
    "MicroQRCode",
]

ALL_ORIENTATIONS = ["horizontal", "vertical", "diagonal"]


class BarcodeStepDialog(QDialog):
    """Editor de paso de lectura de barcodes."""

    def __init__(
        self,
        step: BarcodeStep,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle(self.tr("Lectura de barcodes"))
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["motor1", "motor2"])
        self._engine_combo.setCurrentText(step.engine)
        self._engine_combo.setToolTip(
            self.tr("motor1 = pyzbar (rápido), motor2 = zxing-cpp (más simbologías)")
        )
        layout.addRow(self.tr("Motor:"), self._engine_combo)

        self._symb_edit = QLineEdit(", ".join(step.symbologies))
        self._symb_edit.setPlaceholderText(
            self.tr("Code128, QR, DataMatrix (vacío = todas)")
        )
        layout.addRow(self.tr("Simbologías:"), self._symb_edit)

        self._regex_edit = QLineEdit(step.regex)
        self._regex_edit.setPlaceholderText(
            self.tr("Filtro regex (vacío = sin filtro)")
        )
        self._regex_edit.setToolTip(
            self.tr(
                "Expresión regular para filtrar barcodes por valor. Solo se aceptan los que coincidan"
            )
        )
        layout.addRow(self.tr("Regex:"), self._regex_edit)

        self._regex_symb = QCheckBox(self.tr("Incluir simbología en regex"))
        self._regex_symb.setToolTip(
            self.tr(
                "Si está activo, la regex se evalúa sobre NN + valor, donde NN es "
                "el número de la simbología (Code128 = 02, ITF = 10…)"
            )
        )
        self._regex_symb.setChecked(step.regex_include_symbology)
        layout.addRow("", self._regex_symb)

        self._orient_edit = QLineEdit(", ".join(step.orientations))
        self._orient_edit.setPlaceholderText("horizontal, vertical, diagonal")
        layout.addRow(self.tr("Orientaciones:"), self._orient_edit)

        self._quality = QDoubleSpinBox()
        self._quality.setRange(0.0, 1.0)
        self._quality.setSingleStep(0.1)
        self._quality.setValue(step.quality_threshold)
        self._quality.setToolTip(
            self.tr(
                "Confianza mínima para aceptar un barcode (0.0 = todos, 1.0 = solo perfectos)"
            )
        )
        layout.addRow(self.tr("Umbral calidad:"), self._quality)

        self._window_edit = QLineEdit()
        if step.window:
            self._window_edit.setText(", ".join(str(v) for v in step.window))
        self._window_edit.setPlaceholderText(self.tr("x, y, w, h (vacío = completa)"))
        layout.addRow(self.tr("Ventana:"), self._window_edit)

        layout.addRow(self._build_separator_group(step))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _build_separator_group(self, step: BarcodeStep) -> QGroupBox:
        """Sección «Separador de documento» (mismas claves que FlexibarNET10)."""
        group = QGroupBox(self.tr("Separador de documento"))
        group.setCheckable(True)
        group.setChecked(step.separator_enabled)
        group.setToolTip(
            self.tr(
                "Si un código cumple la condición, la página abre un documento "
                "nuevo. Al reprocesar, la detección pisa la marca manual."
            )
        )
        form = QFormLayout(group)

        self._sep_mode = QComboBox()
        for key, label in SEPARATOR_MODES:
            self._sep_mode.addItem(self.tr(label), key)
        idx = self._sep_mode.findData(step.separator_by)
        self._sep_mode.setCurrentIndex(max(idx, 0))
        form.addRow(self.tr("Condición:"), self._sep_mode)

        self._sep_regex = QLineEdit(step.separator_regex)
        self._sep_regex.setPlaceholderText("^(02|10)")
        form.addRow(self.tr("Regex:"), self._sep_regex)

        self._sep_regex_symb = QCheckBox(self.tr("Evaluar sobre NN + valor"))
        self._sep_regex_symb.setChecked(step.separator_regex_include_symbology)
        self._sep_regex_symb.setToolTip(
            self.tr("Números de simbología: ")
            + ", ".join(f"{name} = {num}" for name, num in legend())
        )
        form.addRow("", self._sep_regex_symb)

        self._sep_symbology = QLineEdit(step.separator_symbology)
        self._sep_symbology.setPlaceholderText("Code39")
        form.addRow(self.tr("Simbología:"), self._sep_symbology)

        self._sep_fixed = QLineEdit(step.separator_fixed_value)
        self._sep_fixed.setPlaceholderText("SEP")
        form.addRow(self.tr("Valor fijo:"), self._sep_fixed)

        hint = QLabel(self.tr("Marca manual en el Workbench (Ctrl+D):"))
        form.addRow(hint)
        self._sep_manual_regex = QLineEdit(step.separator_manual_regex)
        self._sep_manual_regex.setPlaceholderText(r"^\d{8,9}$")
        self._sep_manual_regex.setToolTip(
            self.tr(
                "Valida lo que teclea el operador. No afecta a la detección "
                "automática. Vacío = sin validación"
            )
        )
        form.addRow(self.tr("Regex del valor:"), self._sep_manual_regex)
        self._sep_default = QLineEdit(step.separator_default_value)
        form.addRow(self.tr("Valor por defecto:"), self._sep_default)

        self._sep_group = group
        self._sep_mode.currentIndexChanged.connect(self._update_separator_fields)
        self._update_separator_fields()
        return group

    def _update_separator_fields(self) -> None:
        mode = self._sep_mode.currentData()
        self._sep_regex.setEnabled(mode == "regex")
        self._sep_regex_symb.setEnabled(mode == "regex")
        self._sep_symbology.setEnabled(mode == "symbology")
        self._sep_fixed.setEnabled(mode == "fixed_value")

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

        self._step.separator_enabled = self._sep_group.isChecked()
        self._step.separator_by = self._sep_mode.currentData()
        self._step.separator_regex = self._sep_regex.text().strip()
        self._step.separator_regex_include_symbology = self._sep_regex_symb.isChecked()
        self._step.separator_symbology = self._sep_symbology.text().strip()
        self._step.separator_fixed_value = self._sep_fixed.text().strip()
        self._step.separator_manual_regex = self._sep_manual_regex.text().strip()
        self._step.separator_default_value = self._sep_default.text().strip()

        window_text = self._window_edit.text().strip()
        if window_text:
            parts = [int(p.strip()) for p in window_text.split(",")]
            self._step.window = tuple(parts) if len(parts) == 4 else None
        else:
            self._step.window = None

        return self._step
