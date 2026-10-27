"""Parte inferior del panel derecho del Workbench.

Paridad con FlexibarNET 10: el panel plegable «Campos de lote» (antes una
pestaña) y, debajo, el bloque de pestañas Verificación / OCR / Log, cuyo orden
y visibilidad decide cada aplicación (``app/models/workbench_layout.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QGridLayout,
)

from app.models.workbench_layout import (
    LOG,
    OCR,
    VERIFICACION,
    WorkbenchLayout,
)
from app.ui.workbench.log_panel import LogPanel
from app.ui.workbench.section import CollapsibleSection

# Tope de alto del panel de campos (como Flexibar): con muchos campos hace
# scroll y no empuja las pestañas fuera de la pantalla.
FIELDS_MAX_HEIGHT = 180

# Nombre visible del tipo de campo, bajo su etiqueta.
_TYPE_LABELS = {
    "Texto": "texto",
    "Fecha": "fecha",
    "Número": "número",
    "Lista": "lista",
    "Booleano": "sí/no",
}

log = logging.getLogger(__name__)


class MetadataPanel(QWidget):
    """Panel de campos de lote y pestañas Verificación / OCR / Log.

    Signals:
        batch_field_changed: (nombre_campo, nuevo_valor).
        index_field_changed: (nombre_campo, nuevo_valor).
    """

    batch_field_changed = Signal(str, str)
    index_field_changed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._batch_widgets: dict[str, QWidget] = {}
        # Valor por defecto de cada campo (pestaña Campos de lote)
        self._batch_defaults: dict[str, str] = {}
        self._index_widgets: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Panel «Campos de lote» ---
        self._fields_body = QWidget()
        self._lote_layout = QGridLayout(self._fields_body)
        self._lote_layout.setContentsMargins(0, 0, 4, 0)
        self._lote_layout.setHorizontalSpacing(10)
        self._lote_layout.setVerticalSpacing(10)
        self._lote_layout.setColumnStretch(1, 1)
        self._fields_section = CollapsibleSection(
            self.tr("Campos de lote"),
            self._fields_body,
            max_body_height=FIELDS_MAX_HEIGHT,
        )
        layout.addWidget(self._fields_section)

        # --- Pestañas ---
        self._tabs = QTabWidget()
        self._tabs.setObjectName("infoTabs")
        # Las tres pestañas caben en el ancho del panel: sin flechas de
        # desplazamiento que escondan «Log».
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setUsesScrollButtons(False)

        self._verification_page = QWidget()
        verif_layout = QVBoxLayout(self._verification_page)
        verif_layout.setContentsMargins(0, 0, 0, 0)
        self._verification_hint = QLabel(
            self.tr("Verificación avanzada no configurada en esta aplicación")
        )
        self._verification_hint.setObjectName("emptyHint")
        self._verification_hint.setWordWrap(True)
        self._verification_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        verif_layout.addWidget(self._verification_hint)
        self._verification_tab: QWidget | None = None

        self._ocr_text = QPlainTextEdit()
        self._ocr_text.setObjectName("ocrText")
        self._ocr_text.setReadOnly(True)
        self._ocr_text.setPlaceholderText(self.tr("Esta página no tiene texto OCR"))

        self._log_panel = LogPanel()

        self._tab_pages: dict[str, tuple[QWidget, str]] = {
            VERIFICACION: (self._verification_page, self.tr("Verificación")),
            OCR: (self._ocr_text, self.tr("OCR")),
            LOG: (self._log_panel, self.tr("Log")),
        }
        self._layout = WorkbenchLayout.default()
        self._has_fields = False
        self._rebuild_tabs()
        self._refresh_fields_visibility()
        layout.addWidget(self._tabs, stretch=1)

    # ------------------------------------------------------------------
    # Disposición (paridad FlexibarNET10)
    # ------------------------------------------------------------------

    def apply_layout(self, workbench_layout: WorkbenchLayout) -> None:
        """Aplica el orden y la visibilidad configurados en la aplicación."""
        self._layout = workbench_layout
        self._rebuild_tabs()
        self._refresh_fields_visibility()

    def _rebuild_tabs(self) -> None:
        current = self.current_tab()
        self._tabs.clear()
        for tab_id in self._layout.visible_tabs():
            page, title = self._tab_pages[tab_id]
            self._tabs.addTab(page, title)
        # Sin pestañas visibles no queda una caja vacía ocupando sitio.
        self._tabs.setVisible(self._tabs.count() > 0)
        if current:
            self.select_tab(current)

    def _refresh_fields_visibility(self) -> None:
        from app.models.workbench_layout import CAMPOS

        self._fields_section.setVisible(
            self._has_fields and self._layout.is_visible(CAMPOS)
        )

    def current_tab(self) -> str | None:
        """Id de la pestaña activa (``"ocr"``, ``"log"``…), o None."""
        widget = self._tabs.currentWidget()
        for tab_id, (page, _title) in self._tab_pages.items():
            if page is widget:
                return tab_id
        return None

    def select_tab(self, tab_id: str) -> bool:
        """Activa la pestaña ``tab_id`` si está visible."""
        page = self._tab_pages.get(tab_id, (None, ""))[0]
        idx = self._tabs.indexOf(page) if page is not None else -1
        if idx >= 0:
            self._tabs.setCurrentIndex(idx)
        return idx >= 0

    # ------------------------------------------------------------------
    # Configuración de campos
    # ------------------------------------------------------------------

    def configure(
        self,
        batch_fields_def: list[dict[str, Any]],
        index_fields_def: list[dict[str, Any]] | None = None,
    ) -> None:
        """Crea los widgets de campos según la definición de la app.

        Cada definición es un dict con: name, type, required, choices y,
        opcionalmente, default (valor que se propone en un lote nuevo).
        """
        self._batch_defaults = {
            f.get("name", ""): str(f.get("default", "") or "") for f in batch_fields_def
        }
        self._build_fields(
            batch_fields_def,
            self._lote_layout,
            self._batch_widgets,
            self.batch_field_changed,
        )
        self._has_fields = bool(batch_fields_def)
        self._fields_section.set_count(len(batch_fields_def))
        self._fields_section.fit_body()
        self._refresh_fields_visibility()

    def _build_fields(
        self,
        fields_def: list[dict[str, Any]],
        grid: QGridLayout,
        widgets: dict[str, QWidget],
        signal: Signal,
    ) -> None:
        """Genera widgets dinámicos para cada campo."""
        # Limpiar existentes
        while grid.count():
            item = grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        widgets.clear()

        for row, fdef in enumerate(fields_def):
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
                        n,
                        d.toString(w.displayFormat()),
                    ),
                )

            # Etiqueta como en Flexibar: nombre en seminegrita y, debajo, el
            # tipo en pequeño.
            label_box = QWidget()
            label_layout = QVBoxLayout(label_box)
            label_layout.setContentsMargins(0, 0, 0, 0)
            label_layout.setSpacing(0)
            lbl_name = QLabel(label_text)
            lbl_name.setObjectName("fieldName")
            lbl_type = QLabel(_TYPE_LABELS.get(ftype, ftype.lower()))
            lbl_type.setObjectName("fieldType")
            label_layout.addWidget(lbl_name)
            label_layout.addWidget(lbl_type)
            label_box.setMinimumWidth(100)
            grid.addWidget(label_box, row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(widget, row, 1)

    def _create_field_widget(
        self,
        ftype: str,
        choices: list[str],
        fdef: dict[str, Any] | None = None,
    ) -> QWidget:
        """Crea el widget adecuado según el tipo de campo."""
        fdef = fdef or {}
        name = fdef.get("name", "")
        match ftype:
            case "Fecha":
                w = QDateEdit()
                w.setCalendarPopup(True)
                w.setDate(QDate.currentDate())
                w.setDisplayFormat(fdef.get("date_format", "dd/MM/yyyy"))
                w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                w.setToolTip(self.tr("Seleccionar fecha para «{0}»").format(name))
                return w
            case "Número":
                w = QSpinBox()
                w.setMinimum(int(fdef.get("min", 0)))
                w.setMaximum(int(fdef.get("max", 999999)))
                w.setSingleStep(int(fdef.get("step", 1)))
                w.setToolTip(
                    self.tr("Valor numérico entre {0} y {1}").format(
                        w.minimum(), w.maximum()
                    )
                )
                return w
            case "Booleano":
                w = QCheckBox()
                w.setToolTip(self.tr("Activar/desactivar «{0}»").format(name))
                return w
            case "Lista":
                combo = QComboBox()
                combo.addItems(choices)
                combo.setToolTip(
                    self.tr("Seleccionar una opción para «{0}»").format(name)
                )
                return combo
            case _:  # Texto
                w = QLineEdit()
                w.setToolTip(self.tr("Introducir valor para «{0}»").format(name))
                return w

    # ------------------------------------------------------------------
    # Establecer/obtener valores
    # ------------------------------------------------------------------

    def set_batch_fields(self, values: dict[str, str]) -> None:
        """Carga los valores de los campos de lote.

        Un campo que el lote aún no tiene (lote nuevo) toma su valor por
        defecto, como en FlexibarNET10.
        """
        for name, widget in self._batch_widgets.items():
            val = values.get(name)
            if val is None:
                val = self._batch_defaults.get(name, "")
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
        """Muestra los datos de la página enfocada (pestaña OCR).

        Era un stub vacío: el texto OCR no se veía en ningún sitio. Los
        errores de la página los resume el Workbench en la barra de estado.
        """
        self._ocr_text.setPlainText(ocr_text or "")

    def ocr_text(self) -> str:
        """Texto que muestra la pestaña OCR."""
        return self._ocr_text.toPlainText()

    def set_default_tab(self, tab_name: str) -> None:
        """Activa la pestaña inicial configurada en la aplicación.

        Si no está configurada o está oculta, la primera visible (Flexibar
        ``ResolveInitialTab``). Antes se ignoraba y siempre era la primera.
        """
        target = self._layout.initial_tab(tab_name)
        if target:
            self.select_tab(target)

    def clear(self) -> None:
        """Limpia todos los campos."""
        for widget in self._batch_widgets.values():
            self._set_widget_value(widget, "")

    def add_verification_tab(self, widget: QWidget) -> None:
        """Coloca el panel de verificación de la aplicación en su pestaña."""
        self.remove_verification_tab()
        self._verification_tab = widget
        self._verification_hint.setVisible(False)
        self._verification_page.layout().addWidget(widget)

    def remove_verification_tab(self) -> None:
        """Quita el panel de verificación y vuelve a mostrar el aviso."""
        tab = self._verification_tab
        if tab is not None:
            self._verification_page.layout().removeWidget(tab)
            tab.setParent(None)
            self._verification_tab = None
        self._verification_hint.setVisible(True)

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
            except ValueError, TypeError:
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
