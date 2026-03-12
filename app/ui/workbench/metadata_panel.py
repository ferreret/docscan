"""Panel de metadatos con pestañas: Lote, Indexación, Verificación.

Muestra y edita campos de lote e indexación, y presenta información
de verificación (OCR, IA, errores) en solo lectura.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)


class MetadataPanel(QWidget):
    """Panel derecho inferior con pestañas de metadatos.

    Signals:
        batch_field_changed: (nombre_campo, nuevo_valor).
        index_field_changed: (nombre_campo, nuevo_valor).
    """

    batch_field_changed = Signal(str, str)
    index_field_changed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._batch_widgets: dict[str, QWidget] = {}
        self._index_widgets: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._tabs = QTabWidget()

        # Pestaña Lote
        self._tab_lote = QWidget()
        self._lote_layout = QFormLayout(self._tab_lote)
        lote_scroll = QScrollArea()
        lote_scroll.setWidgetResizable(True)
        lote_scroll.setWidget(self._tab_lote)
        self._tabs.addTab(lote_scroll, "Lote")

        # Pestaña Indexación
        self._tab_index = QWidget()
        self._index_layout = QFormLayout(self._tab_index)
        index_scroll = QScrollArea()
        index_scroll.setWidgetResizable(True)
        index_scroll.setWidget(self._tab_index)
        self._tabs.addTab(index_scroll, "Indexación")

        # Pestaña Verificación
        self._tab_verify = QWidget()
        verify_layout = QVBoxLayout(self._tab_verify)

        self._ocr_text = QPlainTextEdit()
        self._ocr_text.setReadOnly(True)
        self._ocr_text.setMaximumHeight(120)
        verify_layout.addWidget(QLabel("Texto OCR:"))
        verify_layout.addWidget(self._ocr_text)

        self._ai_text = QPlainTextEdit()
        self._ai_text.setReadOnly(True)
        self._ai_text.setMaximumHeight(120)
        verify_layout.addWidget(QLabel("Campos IA:"))
        verify_layout.addWidget(self._ai_text)

        self._errors_text = QPlainTextEdit()
        self._errors_text.setReadOnly(True)
        self._errors_text.setMaximumHeight(80)
        verify_layout.addWidget(QLabel("Errores:"))
        verify_layout.addWidget(self._errors_text)
        verify_layout.addStretch()

        verify_scroll = QScrollArea()
        verify_scroll.setWidgetResizable(True)
        verify_scroll.setWidget(self._tab_verify)
        self._tabs.addTab(verify_scroll, "Verificación")

        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Configuración de campos
    # ------------------------------------------------------------------

    def configure(
        self,
        batch_fields_def: list[dict[str, Any]],
        index_fields_def: list[dict[str, Any]],
    ) -> None:
        """Crea los widgets de campos según la definición de la app.

        Cada definición es un dict con: name, type, required, choices.
        """
        self._build_fields(
            batch_fields_def, self._lote_layout,
            self._batch_widgets, self.batch_field_changed,
        )
        self._build_fields(
            index_fields_def, self._index_layout,
            self._index_widgets, self.index_field_changed,
        )

    def _build_fields(
        self,
        fields_def: list[dict[str, Any]],
        form_layout: QFormLayout,
        widgets: dict[str, QWidget],
        signal: Signal,
    ) -> None:
        """Genera widgets dinámicos para cada campo."""
        # Limpiar existentes
        while form_layout.rowCount() > 0:
            form_layout.removeRow(0)
        widgets.clear()

        for fdef in fields_def:
            name = fdef.get("name", "")
            ftype = fdef.get("type", "Texto")
            choices = fdef.get("choices", [])
            required = fdef.get("required", False)

            label_text = f"{name}{'*' if required else ''}"
            widget = self._create_field_widget(ftype, choices, fdef)
            widgets[name] = widget

            # Conectar cambio
            if isinstance(widget, QLineEdit):
                widget.editingFinished.connect(
                    lambda n=name, w=widget: signal.emit(n, w.text()),
                )
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(
                    lambda val, n=name: signal.emit(n, val),
                )
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(
                    lambda val, n=name: signal.emit(n, str(val)),
                )
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(
                    lambda val, n=name: signal.emit(n, str(val)),
                )

            form_layout.addRow(label_text, widget)

    def _create_field_widget(
        self,
        ftype: str,
        choices: list[str],
        fdef: dict[str, Any] | None = None,
    ) -> QWidget:
        """Crea el widget adecuado según el tipo de campo."""
        fdef = fdef or {}
        match ftype:
            case "Fecha":
                return QDateEdit()
            case "Número":
                w = QSpinBox()
                w.setMinimum(int(fdef.get("min", 0)))
                w.setMaximum(int(fdef.get("max", 999999)))
                w.setSingleStep(int(fdef.get("step", 1)))
                return w
            case "Booleano":
                return QCheckBox()
            case "Lista":
                combo = QComboBox()
                combo.addItems(choices)
                return combo
            case _:  # Texto
                return QLineEdit()

    # ------------------------------------------------------------------
    # Establecer/obtener valores
    # ------------------------------------------------------------------

    def set_batch_fields(self, values: dict[str, str]) -> None:
        """Carga los valores de los campos de lote."""
        for name, widget in self._batch_widgets.items():
            val = values.get(name, "")
            self._set_widget_value(widget, val)

    def set_index_fields(self, values: dict[str, str]) -> None:
        """Carga los valores de los campos de indexación."""
        for name, widget in self._index_widgets.items():
            val = values.get(name, "")
            self._set_widget_value(widget, val)

    def get_batch_fields(self) -> dict[str, str]:
        """Devuelve los valores actuales de los campos de lote."""
        return {
            name: self._get_widget_value(widget)
            for name, widget in self._batch_widgets.items()
        }

    def get_index_fields(self) -> dict[str, str]:
        """Devuelve los valores actuales de los campos de indexación."""
        return {
            name: self._get_widget_value(widget)
            for name, widget in self._index_widgets.items()
        }

    def set_verification_data(
        self,
        ocr_text: str = "",
        ai_fields_json: str = "{}",
        errors_json: str = "[]",
        script_errors_json: str = "[]",
    ) -> None:
        """Actualiza la pestaña de verificación."""
        self._ocr_text.setPlainText(ocr_text)

        try:
            ai = json.loads(ai_fields_json)
            self._ai_text.setPlainText(
                json.dumps(ai, ensure_ascii=False, indent=2),
            )
        except (json.JSONDecodeError, TypeError):
            self._ai_text.setPlainText(ai_fields_json)

        errors = []
        try:
            errors.extend(json.loads(errors_json))
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            errors.extend(json.loads(script_errors_json))
        except (json.JSONDecodeError, TypeError):
            pass
        self._errors_text.setPlainText("\n".join(str(e) for e in errors))

    def set_default_tab(self, tab_name: str) -> None:
        """Selecciona la pestaña por defecto."""
        tab_map = {"lote": 0, "indexacion": 1, "verificacion": 2}
        idx = tab_map.get(tab_name, 0)
        self._tabs.setCurrentIndex(idx)

    def clear(self) -> None:
        """Limpia todos los campos."""
        for widget in self._batch_widgets.values():
            self._set_widget_value(widget, "")
        for widget in self._index_widgets.values():
            self._set_widget_value(widget, "")
        self._ocr_text.clear()
        self._ai_text.clear()
        self._errors_text.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_widget_value(widget: QWidget, value: str) -> None:
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(value)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(value.lower() in ("true", "1"))
        elif isinstance(widget, QSpinBox):
            try:
                widget.setValue(int(float(value)))
            except (ValueError, TypeError):
                widget.setValue(0)

    @staticmethod
    def _get_widget_value(widget: QWidget) -> str:
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QCheckBox):
            return str(widget.isChecked())
        elif isinstance(widget, QSpinBox):
            return str(widget.value())
        return ""
