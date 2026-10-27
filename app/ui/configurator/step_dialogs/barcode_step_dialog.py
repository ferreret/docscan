"""Diálogo de edición de paso Barcode.

Presentación del editor de FlexibarNET10 (manual, «Paso Barcode»): las
opciones del lector por secciones —Simbologías, Lectura, Imagen, Filtrado y
Avanzado— y, después, el separador de documento en dos bloques, Detección
automática y Marca manual. Solo cambia la presentación: los campos de
``BarcodeStep`` y su significado son los de siempre.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.steps import BarcodeStep
from app.services.barcode_service import MOTOR1_SYMBOLOGIES
from app.utils.symbology_numbers import legend

# (clave guardada, etiqueta) del modo de detección de separador, en el orden
# del combo de Flexibar
SEPARATOR_MODES = [
    ("symbology", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Por simbología")),
    ("regex", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Por expresión regular")),
    ("fixed_value", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Por valor fijo")),
]

# Simbologías por familia, como las casillas de Flexibar. Los nombres son los
# de DocScan (los que entienden los dos motores de barcode_service).
SYMBOLOGY_FAMILIES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        QT_TRANSLATE_NOOP("BarcodeStepDialog", "1D lineal"),
        [
            ("Code39", "Code39"),
            ("Code128", "Code128"),
            ("Code93", "Code93"),
            ("Codabar", "Codabar"),
            ("ITF", "Interleaved 2 of 5"),
        ],
    ),
    (
        QT_TRANSLATE_NOOP("BarcodeStepDialog", "EAN/UPC"),
        [
            ("EAN13", "EAN13"),
            ("EAN8", "EAN8"),
            ("UPCA", "UPCA"),
            ("UPCE", "UPCE"),
        ],
    ),
    (
        QT_TRANSLATE_NOOP("BarcodeStepDialog", "2D"),
        [
            ("QR", "QR"),
            ("MicroQRCode", "MicroQR"),
            ("DataMatrix", "DataMatrix"),
            ("PDF417", "PDF417"),
            ("Aztec", "Aztec"),
            ("MaxiCode", "MaxiCode"),
        ],
    ),
]

ALL_SYMBOLOGIES = [name for _, items in SYMBOLOGY_FAMILIES for name, _ in items]

# Las que pyzbar (motor 1) no lee: solo las encuentra zxing-cpp (motor 2)
MOTOR2_ONLY = {name for name in ALL_SYMBOLOGIES if name not in MOTOR1_SYMBOLOGIES}

ALL_ORIENTATIONS = [
    ("horizontal", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Horizontal")),
    ("vertical", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Vertical")),
    ("diagonal", QT_TRANSLATE_NOOP("BarcodeStepDialog", "Ángulo 45/135")),
]


def _tr(text: str) -> str:
    return QCoreApplication.translate("BarcodeStepDialog", text)


def legend_text() -> str:
    """Leyenda de números de simbología («Code39 = 01 · Code128 = 02 · …»)."""
    return " · ".join(f"{name} = {num}" for name, num in legend())


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
        self.setMinimumWidth(620)
        self.resize(680, 760)

        outer = QVBoxLayout(self)

        body = QWidget()
        sections = QVBoxLayout(body)
        sections.setContentsMargins(0, 0, 6, 0)
        sections.setSpacing(10)

        lbl_reader = QLabel(self.tr("CONFIGURACIÓN DEL LECTOR"))
        lbl_reader.setObjectName("sectionTitle")
        sections.addWidget(lbl_reader)
        sections.addWidget(self._build_symbologies(step))
        sections.addWidget(self._build_reading(step))
        sections.addWidget(self._build_image(step))
        sections.addWidget(self._build_filtering(step))
        sections.addWidget(self._build_advanced())

        lbl_sep = QLabel(self.tr("SEPARADOR DE DOCUMENTO"))
        lbl_sep.setObjectName("sectionTitle")
        sections.addWidget(lbl_sep)
        sections.addWidget(self._build_separator_auto(step))
        sections.addWidget(self._build_separator_manual(step))
        sections.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._update_separator_fields()
        self._connect_json_refresh(body)
        self._refresh_json()

    # ------------------------------------------------------------------
    # Secciones del lector
    # ------------------------------------------------------------------

    def _build_symbologies(self, step: BarcodeStep) -> QGroupBox:
        """Sección «Simbologías»: una casilla por simbología, por familias."""
        group = QGroupBox(self.tr("Simbologías"))
        layout = QVBoxLayout(group)
        self._symb_checks: dict[str, QCheckBox] = {}
        families = QHBoxLayout()
        families.setSpacing(18)
        for family, items in SYMBOLOGY_FAMILIES:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(_tr(family))
            lbl.setObjectName("fieldName")
            col.addWidget(lbl)
            for name, label in items:
                check = QCheckBox(label)
                check.setChecked(name in step.symbologies)
                if name in MOTOR2_ONLY:
                    check.setToolTip(self.tr("Solo la lee el motor 2 (zxing-cpp)"))
                self._symb_checks[name] = check
                col.addWidget(check)
            col.addStretch(1)
            families.addLayout(col)
        families.addStretch(1)
        layout.addLayout(families)

        # Nombres que el editor no conoce (escritos a mano en versiones
        # anteriores): se conservan tal cual al guardar.
        self._extra_symbologies = [
            s for s in step.symbologies if s not in self._symb_checks
        ]
        hint = self.tr("Ninguna marcada = todas las que lee el motor.")
        if self._extra_symbologies:
            hint += " " + self.tr("Se conservan además: {0}").format(
                ", ".join(self._extra_symbologies)
            )
        lbl_hint = QLabel(hint)
        lbl_hint.setObjectName("hint_label")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)
        return group

    def _build_reading(self, step: BarcodeStep) -> QGroupBox:
        """Sección «Lectura»: motor, orientaciones y confianza mínima."""
        group = QGroupBox(self.tr("Lectura"))
        form = QFormLayout(group)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["motor1", "motor2"])
        self._engine_combo.setCurrentText(step.engine)
        self._engine_combo.setToolTip(
            self.tr("motor1 = pyzbar (rápido), motor2 = zxing-cpp (más simbologías)")
        )
        form.addRow(self.tr("Motor:"), self._engine_combo)

        orient_row = QHBoxLayout()
        self._orient_checks: dict[str, QCheckBox] = {}
        for key, label in ALL_ORIENTATIONS:
            check = QCheckBox(_tr(label))
            check.setChecked(key in step.orientations)
            self._orient_checks[key] = check
            orient_row.addWidget(check)
        orient_row.addStretch(1)
        self._extra_orientations = [
            o for o in step.orientations if o not in self._orient_checks
        ]
        form.addRow(self.tr("Orientación:"), orient_row)

        self._quality = QDoubleSpinBox()
        self._quality.setRange(0.0, 1.0)
        self._quality.setSingleStep(0.1)
        self._quality.setValue(step.quality_threshold)
        self._quality.setToolTip(
            self.tr(
                "Confianza mínima para aceptar un barcode (0.0 = todos, 1.0 = solo perfectos)"
            )
        )
        form.addRow(self.tr("Confianza mínima:"), self._quality)
        return group

    def _build_image(self, step: BarcodeStep) -> QGroupBox:
        """Sección «Imagen»: región de escaneo (todo a 0 = página completa)."""
        group = QGroupBox(self.tr("Imagen"))
        form = QFormLayout(group)
        region = QGridLayout()
        self._window_spins: list[QSpinBox] = []
        values = step.window or (0, 0, 0, 0)
        for i, (label, value) in enumerate(
            zip(
                (self.tr("X"), self.tr("Y"), self.tr("Ancho"), self.tr("Alto")),
                values,
                strict=True,
            )
        ):
            spin = QSpinBox()
            spin.setRange(0, 100000)
            spin.setValue(int(value))
            spin.setSuffix(" px")
            spin.setMinimumWidth(110)
            row, col = divmod(i, 2)
            region.addWidget(QLabel(label), row, col * 2)
            region.addWidget(spin, row, col * 2 + 1)
            self._window_spins.append(spin)
        region.setColumnStretch(4, 1)
        form.addRow(self.tr("Región de escaneo:"), region)
        hint = QLabel(self.tr("Todo a 0 = página completa."))
        hint.setObjectName("hint_label")
        form.addRow("", hint)
        return group

    def _build_filtering(self, step: BarcodeStep) -> QGroupBox:
        """Sección «Filtrado»: regex tras lectura y leyenda de simbologías."""
        group = QGroupBox(self.tr("Filtrado"))
        form = QFormLayout(group)

        self._regex_edit = QLineEdit(step.regex)
        self._regex_edit.setPlaceholderText(
            self.tr("Filtro regex (vacío = sin filtro)")
        )
        self._regex_edit.setToolTip(
            self.tr(
                "Expresión regular para filtrar barcodes por valor. Solo se aceptan los que coincidan"
            )
        )
        form.addRow(self.tr("Expresión regular:"), self._regex_edit)

        self._regex_symb = QCheckBox(self.tr("Incluir simbología en regex"))
        self._regex_symb.setToolTip(
            self.tr(
                "Si está activo, la regex se evalúa sobre NN + valor, donde NN es "
                "el número de la simbología (Code128 = 02, ITF = 10…)"
            )
        )
        self._regex_symb.setChecked(step.regex_include_symbology)
        form.addRow("", self._regex_symb)
        form.addRow("", self._legend_label())
        return group

    def _build_advanced(self) -> QGroupBox:
        """Sección «Avanzado»: la configuración del paso tal como se guarda."""
        group = QGroupBox(self.tr("Avanzado"))
        layout = QVBoxLayout(group)
        hint = QLabel(
            self.tr(
                "Configuración del paso en JSON, tal como se guarda en el "
                "pipeline. Se actualiza con el formulario."
            )
        )
        hint.setObjectName("hint_label")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._json_view = QPlainTextEdit()
        self._json_view.setObjectName("codeEditor")
        self._json_view.setReadOnly(True)
        self._json_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._json_view.setFixedHeight(150)
        layout.addWidget(self._json_view)
        return group

    def _legend_label(self) -> QLabel:
        """Leyenda visible de números de simbología (NN de «NN + valor»)."""
        lbl = QLabel(self.tr("Números de simbología: ") + legend_text())
        lbl.setObjectName("symbologyLegend")
        lbl.setWordWrap(True)
        return lbl

    # ------------------------------------------------------------------
    # Separador de documento
    # ------------------------------------------------------------------

    def _build_separator_auto(self, step: BarcodeStep) -> QGroupBox:
        """Bloque «Detección automática» (mismas claves que FlexibarNET10)."""
        group = QGroupBox(self.tr("Detección automática"))
        layout = QVBoxLayout(group)

        self._sep_auto = QCheckBox(self.tr("Detectar separador automáticamente"))
        self._sep_auto.setChecked(step.separator_enabled)
        self._sep_auto.setToolTip(
            self.tr(
                "Si un código cumple la condición, la página abre un documento "
                "nuevo. Al reprocesar, la detección pisa la marca manual."
            )
        )
        layout.addWidget(self._sep_auto)

        self._sep_auto_body = QWidget()
        form = QFormLayout(self._sep_auto_body)
        form.setContentsMargins(0, 0, 0, 0)
        self._sep_form = form

        self._sep_mode = QComboBox()
        for key, label in SEPARATOR_MODES:
            self._sep_mode.addItem(_tr(label), key)
        idx = self._sep_mode.findData(step.separator_by)
        self._sep_mode.setCurrentIndex(max(idx, 0))
        form.addRow(self.tr("Condición:"), self._sep_mode)

        self._sep_symbology = QLineEdit(step.separator_symbology)
        self._sep_symbology.setPlaceholderText("Code39")
        form.addRow(self.tr("Simbología:"), self._sep_symbology)

        self._sep_regex = QLineEdit(step.separator_regex)
        self._sep_regex.setPlaceholderText("^(02|10)")
        form.addRow(self.tr("Expresión regular del valor:"), self._sep_regex)

        self._sep_regex_symb = QCheckBox(self.tr("Incluir simbología en la expresión"))
        self._sep_regex_symb.setChecked(step.separator_regex_include_symbology)
        self._sep_regex_symb.setToolTip(
            self.tr("La expresión se evalúa sobre NN + valor (NN, de la leyenda)")
        )
        form.addRow("", self._sep_regex_symb)
        self._sep_legend = self._legend_label()
        form.addRow("", self._sep_legend)

        self._sep_fixed = QLineEdit(step.separator_fixed_value)
        self._sep_fixed.setPlaceholderText("SEP")
        form.addRow(self.tr("Valor exacto:"), self._sep_fixed)

        layout.addWidget(self._sep_auto_body)

        self._sep_mode.currentIndexChanged.connect(self._update_separator_fields)
        self._sep_auto.toggled.connect(self._update_separator_fields)
        return group

    def _build_separator_manual(self, step: BarcodeStep) -> QGroupBox:
        """Bloque «Marca manual»: valida lo que teclea el operador (Ctrl+D)."""
        group = QGroupBox(self.tr("Marca manual"))
        form = QFormLayout(group)
        hint = QLabel(
            self.tr(
                "Al marcar o editar un separador a mano en el Workbench (Ctrl+D). "
                "No afecta a la detección automática."
            )
        )
        hint.setObjectName("hint_label")
        hint.setWordWrap(True)
        form.addRow(hint)

        self._sep_manual_regex = QLineEdit(step.separator_manual_regex)
        self._sep_manual_regex.setPlaceholderText(r"^\d{8,9}$")
        self._sep_manual_regex.setToolTip(
            self.tr(
                "Valida lo que teclea el operador, sin la simbología. "
                "Vacío = sin validación"
            )
        )
        form.addRow(self.tr("Validación del valor (regex):"), self._sep_manual_regex)
        self._sep_default = QLineEdit(step.separator_default_value)
        self._sep_default.setToolTip(
            self.tr("Valor con el que se propone la marca si la página no tiene código")
        )
        form.addRow(self.tr("Valor por defecto:"), self._sep_default)
        return group

    def _update_separator_fields(self) -> None:
        """Muestra solo el campo de la condición elegida, como Flexibar."""
        mode = self._sep_mode.currentData()
        self._sep_auto_body.setEnabled(self._sep_auto.isChecked())
        by_mode = {
            "symbology": (self._sep_symbology,),
            "regex": (self._sep_regex, self._sep_regex_symb, self._sep_legend),
            "fixed_value": (self._sep_fixed,),
        }
        for key, widgets in by_mode.items():
            for w in widgets:
                w.setEnabled(key == mode)
                self._sep_form.setRowVisible(w, key == mode)

    # ------------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------------

    def _connect_json_refresh(self, root: QWidget) -> None:
        """Refresca la vista JSON de «Avanzado» con cualquier cambio."""
        for w in root.findChildren(QCheckBox):
            w.toggled.connect(self._refresh_json)
        for w in root.findChildren(QLineEdit):
            if w.parent() is not None and isinstance(w.parent(), QSpinBox):
                continue
            w.textChanged.connect(self._refresh_json)
        for w in root.findChildren(QComboBox):
            w.currentIndexChanged.connect(self._refresh_json)
        for w in root.findChildren(QSpinBox) + root.findChildren(QDoubleSpinBox):
            w.valueChanged.connect(self._refresh_json)

    def _refresh_json(self, *_args) -> None:
        preview = self._collect(replace(self._step))
        data = asdict(preview)
        self._json_view.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))

    def _collect(self, step: BarcodeStep) -> BarcodeStep:
        """Vuelca el formulario sobre ``step`` y lo devuelve."""
        step.engine = self._engine_combo.currentText()
        step.symbologies = [
            name for name, check in self._symb_checks.items() if check.isChecked()
        ] + list(self._extra_symbologies)
        step.regex = self._regex_edit.text().strip()
        step.regex_include_symbology = self._regex_symb.isChecked()
        step.orientations = [
            key for key, check in self._orient_checks.items() if check.isChecked()
        ] + list(self._extra_orientations)
        step.quality_threshold = self._quality.value()

        step.separator_enabled = self._sep_auto.isChecked()
        step.separator_by = self._sep_mode.currentData()
        step.separator_regex = self._sep_regex.text().strip()
        step.separator_regex_include_symbology = self._sep_regex_symb.isChecked()
        step.separator_symbology = self._sep_symbology.text().strip()
        step.separator_fixed_value = self._sep_fixed.text().strip()
        step.separator_manual_regex = self._sep_manual_regex.text().strip()
        step.separator_default_value = self._sep_default.text().strip()

        window = tuple(spin.value() for spin in self._window_spins)
        step.window = window if any(window) else None
        return step

    def get_step(self) -> BarcodeStep:
        return self._collect(self._step)
