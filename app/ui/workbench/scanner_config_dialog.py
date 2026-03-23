"""Diálogo dinámico de configuración del escáner (SANE).

Consulta las opciones reales del dispositivo conectado y genera
controles apropiados para cada opción: combos para listas, sliders
para rangos numéricos, checkboxes para booleanos.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.scanner_service import DeviceOption

log = logging.getLogger(__name__)

# Opciones que se muestran en el diálogo (las que realmente interesan)
_COMMON_OPTIONS = {
    "source", "mode", "resolution",
    "brightness", "contrast", "threshold",
    "df_thickness", "df_length",
    "rollerdeskew", "swdeskew", "swdespeck", "swcrop", "swskip",
    "stapledetect", "buffermode",
    "dropout_front", "dropout_back",
    "duplex",
}


class ScannerConfigDialog(QDialog):
    """Diálogo que muestra las opciones reales de un dispositivo SANE."""

    def __init__(
        self,
        options: list[DeviceOption],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración del escáner")
        self.setMinimumWidth(420)
        self.setMinimumHeight(300)
        self._options = options
        self._widgets: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Scroll area para muchas opciones
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._form = QFormLayout(container)
        self._form.setVerticalSpacing(6)
        self._form.setContentsMargins(8, 8, 8, 8)

        for opt in self._options:
            if opt.name not in _COMMON_OPTIONS:
                continue
            widget = self._create_widget(opt)
            if widget is not None:
                self._widgets[opt.name] = widget
                # Sufijo de unidad
                unit_suffix = self._unit_label(opt.unit)
                label = opt.title
                if unit_suffix:
                    label += f" ({unit_suffix})"
                self._form.addRow(f"{label}:", widget)
                if opt.description:
                    widget.setToolTip(opt.description)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Botones OK/Cancelar
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_widget(self, opt: DeviceOption) -> QWidget | None:
        """Crea el widget apropiado según el tipo y constraint de la opción."""
        if opt.type == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(opt.value))
            return cb

        if opt.type == "string":
            if isinstance(opt.constraint, list):
                combo = QComboBox()
                combo.addItems(opt.constraint)
                if opt.value in opt.constraint:
                    combo.setCurrentText(str(opt.value))
                return combo
            return None  # String libre sin constraint → no mostrar

        if opt.type in ("int", "fixed"):
            if isinstance(opt.constraint, list):
                # Lista de valores discretos → combo
                combo = QComboBox()
                for v in opt.constraint:
                    combo.addItem(str(v), v)
                if opt.value is not None:
                    for i in range(combo.count()):
                        if combo.itemData(i) == opt.value:
                            combo.setCurrentIndex(i)
                            break
                return combo

            if isinstance(opt.constraint, tuple) and len(opt.constraint) == 3:
                lo, hi, step = opt.constraint
                if opt.type == "fixed":
                    spin = QDoubleSpinBox()
                    spin.setRange(float(lo), float(hi))
                    spin.setSingleStep(float(step) if step else 0.1)
                    spin.setDecimals(2)
                    if opt.value is not None:
                        spin.setValue(float(opt.value))
                    return spin
                else:
                    spin = QSpinBox()
                    spin.setRange(int(lo), int(hi))
                    spin.setSingleStep(int(step) if step else 1)
                    if opt.value is not None:
                        spin.setValue(int(opt.value))
                    return spin

            # Sin constraint → spin libre
            if opt.type == "int":
                spin = QSpinBox()
                spin.setRange(-999999, 999999)
                if opt.value is not None:
                    spin.setValue(int(opt.value))
                return spin

        return None

    def _unit_label(self, unit: str) -> str:
        """Devuelve un sufijo legible para la unidad."""
        return {
            "dpi": "DPI",
            "mm": "mm",
            "pixel": "px",
            "percent": "%",
            "microsecond": "μs",
            "bit": "bit",
        }.get(unit, "")

    def get_selected_options(self) -> dict[str, Any]:
        """Devuelve un dict {nombre_opción: valor} con los valores seleccionados."""
        result: dict[str, Any] = {}
        for opt_name, widget in self._widgets.items():
            opt = next((o for o in self._options if o.name == opt_name), None)
            if opt is None:
                continue

            if isinstance(widget, QCheckBox):
                result[opt_name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                data = widget.currentData()
                if data is not None:
                    result[opt_name] = data
                else:
                    result[opt_name] = widget.currentText()
            elif isinstance(widget, QDoubleSpinBox):
                result[opt_name] = widget.value()
            elif isinstance(widget, QSpinBox):
                result[opt_name] = widget.value()

        return result
