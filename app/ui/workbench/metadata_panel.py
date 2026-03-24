"""Panel de metadatos — pestaña de índices de lote.

Muestra y edita campos de lote definidos por la aplicación.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.workbench.log_panel import LogPanel

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

        # Pestaña Lote (única pestaña activa por ahora)
        self._tab_lote = QWidget()
        self._lote_layout = QFormLayout(self._tab_lote)
        self._lote_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._lote_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self._lote_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self._lote_layout.setVerticalSpacing(8)
        self._lote_layout.setContentsMargins(6, 8, 6, 8)
        lote_scroll = QScrollArea()
        lote_scroll.setWidgetResizable(True)
        lote_scroll.setWidget(self._tab_lote)
        self._tabs.addTab(lote_scroll, self.tr("Lote"))

        # Pestaña Log
        self._log_panel = LogPanel()
        self._tabs.addTab(self._log_panel, self.tr("Log"))

        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Configuración de campos
    # ------------------------------------------------------------------

    def configure(
        self,
        batch_fields_def: list[dict[str, Any]],
        index_fields_def: list[dict[str, Any]] | None = None,
    ) -> None:
        """Crea los widgets de campos según la definición de la app.

        Cada definición es un dict con: name, type, required, choices.
        """
        self._build_fields(
            batch_fields_def, self._lote_layout,
            self._batch_widgets, self.batch_field_changed,
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
            elif isinstance(widget, QDateEdit):
                widget.dateChanged.connect(
                    lambda d, n=name, w=widget: signal.emit(
                        n, d.toString(w.displayFormat()),
                    ),
                )

            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setMinimumWidth(80)
            form_layout.addRow(lbl, widget)

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
                w = QDateEdit()
                w.setCalendarPopup(True)
                w.setDate(QDate.currentDate())
                w.setDisplayFormat(fdef.get("date_format", "dd/MM/yyyy"))
                w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                return w
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
        """Stub — indexación desactivada temporalmente."""
        pass

    def get_batch_fields(self) -> dict[str, str]:
        """Devuelve los valores actuales de los campos de lote."""
        return {
            name: self._get_widget_value(widget)
            for name, widget in self._batch_widgets.items()
        }

    def get_index_fields(self) -> dict[str, str]:
        """Stub — indexación desactivada temporalmente."""
        return {}

    def set_verification_data(
        self,
        ocr_text: str = "",
        fields_json: str = "{}",
        errors_json: str = "[]",
        script_errors_json: str = "[]",
    ) -> None:
        """Stub — verificación desactivada temporalmente."""
        pass

    def set_default_tab(self, tab_name: str) -> None:
        """Selecciona la pestaña por defecto."""
        self._tabs.setCurrentIndex(0)

    def clear(self) -> None:
        """Limpia todos los campos."""
        for widget in self._batch_widgets.values():
            self._set_widget_value(widget, "")

    def add_verification_tab(self, widget: QWidget) -> None:
        """Inserta la pestaña de verificación entre Lote y Log."""
        self._verification_tab = widget
        self._tabs.insertTab(1, widget, self.tr("Verificación"))

    def remove_verification_tab(self) -> None:
        """Elimina la pestaña de verificación si existe."""
        tab = getattr(self, "_verification_tab", None)
        if tab is not None:
            idx = self._tabs.indexOf(tab)
            if idx >= 0:
                self._tabs.removeTab(idx)
            self._verification_tab = None

    def cleanup(self) -> None:
        """Libera recursos (handler de logging + panel verificación)."""
        self.remove_verification_tab()
        self._log_panel.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_widget_value(widget: QWidget, value: str) -> None:
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QDateEdit):
            date = QDate.fromString(value, widget.displayFormat())
            if date.isValid():
                widget.setDate(date)
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
        elif isinstance(widget, QDateEdit):
            return widget.date().toString(widget.displayFormat())
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QCheckBox):
            return str(widget.isChecked())
        elif isinstance(widget, QSpinBox):
            return str(widget.value())
        return ""
