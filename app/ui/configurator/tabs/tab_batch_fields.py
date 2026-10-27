"""Pestaña de Campos de Lote del configurador.

Maestro-detalle como FlexibarNET10: la lista de campos a la izquierda (nombre
y, debajo, tipo y «· obligatorio») y, a la derecha, el editor del campo
seleccionado. Cada campo tiene:

- Nombre (``label``): etiqueta en el Workbench y clave del valor del lote.
- Tipo: texto, fecha, lista predefinida o numérico (min/max/step).
- Obligatorio (sí/no).
- Valor por defecto (``default``): se propone al abrir un lote nuevo.
- Descripción (``description``): nota interna; el operador no la ve.

Los campos se serializan en ``Application.batch_fields_json``. Al guardar se
conservan las claves que esta pestaña no edita.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QSize, QT_TRANSLATE_NOOP, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application

log = logging.getLogger(__name__)

# Tipos de campo disponibles
FIELD_TYPES = ["texto", "fecha", "lista", "numérico"]

# Claves de ``config`` que pertenecen a cada tipo. Al cambiar de tipo se
# quitan las del tipo anterior; cualquier otra clave se conserva.
_TYPED_CONFIG_KEYS = {
    "lista": ("values",),
    "numérico": ("min", "max", "step"),
    "fecha": ("format",),
}
_ALL_TYPED_KEYS = {k for keys in _TYPED_CONFIG_KEYS.values() for k in keys}

# Alto de cada fila de la lista de campos
ROW_HEIGHT = 46

DATE_FORMATS = ["dd/MM/yyyy", "yyyy-MM-dd", "dd-MM-yyyy", "MM/dd/yyyy"]

_REQUIRED_SRC = QT_TRANSLATE_NOOP("BatchFieldsTab", "obligatorio")
_UNNAMED_SRC = QT_TRANSLATE_NOOP("BatchFieldsTab", "(sin nombre)")


def _tr(text: str) -> str:
    return QCoreApplication.translate("BatchFieldsTab", text)


def field_summary(field: dict[str, Any]) -> tuple[str, str]:
    """Las dos líneas de la fila: nombre y «tipo · obligatorio»."""
    name = str(field.get("label", "")).strip() or _tr(_UNNAMED_SRC)
    meta = str(field.get("type", "texto"))
    if field.get("required"):
        meta += f" · {_tr(_REQUIRED_SRC)}"
    return name, meta


class _FieldRow(QWidget):
    """Fila de la lista: nombre en seminegrita y, debajo, tipo en pequeño."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)
        self.lbl_name = QLabel()
        self.lbl_name.setObjectName("fieldName")
        self.lbl_meta = QLabel()
        self.lbl_meta.setObjectName("fieldType")
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_meta)

    def set_field(self, field: dict[str, Any]) -> None:
        name, meta = field_summary(field)
        self.lbl_name.setText(name)
        self.lbl_meta.setText(meta)


class BatchFieldsTab(QWidget):
    """Pestaña para definir campos de lote dinámicos."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Copia de cada campo tal como viene del JSON: el editor solo toca
        # las claves que muestra, el resto llega intacto a apply_to.
        self._fields: list[dict[str, Any]] = []
        self._current = -1
        self._loading = False
        self._setup_ui()
        self._load_fields(app)

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # --- Lista de campos ---
        left = QWidget()
        left.setObjectName("fieldsPanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        toolbar = QHBoxLayout()
        btn_add = QPushButton(self.tr("+ Añadir campo"))
        btn_add.setProperty("cssClass", "primary")
        btn_add.setToolTip(self.tr("Añadir un nuevo campo de lote a la aplicación"))
        btn_add.clicked.connect(self._add_empty_row)
        toolbar.addWidget(btn_add)
        self._btn_remove = QPushButton(self.tr("✕ Eliminar"))
        self._btn_remove.setProperty("cssClass", "danger")
        self._btn_remove.setToolTip(self.tr("Eliminar el campo seleccionado"))
        self._btn_remove.clicked.connect(lambda: self._remove_row(self._current))
        toolbar.addWidget(self._btn_remove)
        toolbar.addStretch(1)
        self._btn_up = QPushButton("▲")
        self._btn_up.setFixedWidth(30)
        self._btn_up.setToolTip(self.tr("Subir"))
        self._btn_up.clicked.connect(lambda: self._move_row(self._current, -1))
        toolbar.addWidget(self._btn_up)
        self._btn_down = QPushButton("▼")
        self._btn_down.setFixedWidth(30)
        self._btn_down.setToolTip(self.tr("Bajar"))
        self._btn_down.clicked.connect(lambda: self._move_row(self._current, 1))
        toolbar.addWidget(self._btn_down)
        ll.addLayout(toolbar)

        self._list = QListWidget()
        self._list.setObjectName("fieldList")
        self._list.currentRowChanged.connect(self._on_row_changed)
        ll.addWidget(self._list)
        splitter.addWidget(left)

        # --- Detalle ---
        self._detail_stack = QStackedWidget()
        empty = QLabel(self.tr("Sin campo seleccionado"))
        empty.setObjectName("emptyHint")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_stack.addWidget(empty)
        self._detail_stack.addWidget(self._build_detail())
        splitter.addWidget(self._detail_stack)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([320, 580])

    def _build_detail(self) -> QWidget:
        detail = QFrame()
        detail.setObjectName("fieldDetail")
        outer = QVBoxLayout(detail)
        outer.setContentsMargins(12, 4, 4, 4)
        lbl = QLabel(self.tr("CAMPO SELECCIONADO"))
        lbl.setObjectName("sectionTitle")
        outer.addWidget(lbl)
        form = QFormLayout()
        form.setSpacing(8)
        outer.addLayout(form)
        outer.addStretch(1)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText(self.tr("Nombre del campo..."))
        self._label_edit.setToolTip(
            self.tr(
                "Etiqueta en el workbench y clave del valor en scripts y transferencia"
            )
        )
        self._label_edit.textChanged.connect(self._store_current)
        form.addRow(self.tr("Nombre del campo:"), self._label_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(FIELD_TYPES)
        self._type_combo.setToolTip(
            self.tr("Tipo de dato: texto, fecha, lista desplegable o numérico")
        )
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow(self.tr("Tipo:"), self._type_combo)

        self._required_check = QCheckBox(self.tr("Obligatorio"))
        self._required_check.setToolTip(
            self.tr("Marcar si este campo es obligatorio antes de transferir")
        )
        self._required_check.toggled.connect(self._store_current)
        form.addRow("", self._required_check)

        self._default_edit = QLineEdit()
        self._default_edit.setToolTip(
            self.tr(
                "Valor que aparece pre-rellenado al abrir un lote nuevo. "
                "Vacío = sin valor (en las fechas, hoy)"
            )
        )
        self._default_edit.textChanged.connect(self._store_current)
        form.addRow(self.tr("Valor por defecto:"), self._default_edit)

        self._description_edit = QPlainTextEdit()
        self._description_edit.setFixedHeight(60)
        self._description_edit.setToolTip(
            self.tr(
                "Nota interna para el equipo de configuración; el operador no la ve"
            )
        )
        self._description_edit.textChanged.connect(self._store_current)
        form.addRow(self.tr("Descripción:"), self._description_edit)

        self._config_stack = QStackedWidget()
        self._config_pages: dict[str, int] = {}
        self._config_pages["texto"] = self._config_stack.addWidget(
            self._make_text_config()
        )
        self._config_pages["lista"] = self._config_stack.addWidget(
            self._make_list_config()
        )
        self._config_pages["numérico"] = self._config_stack.addWidget(
            self._make_numeric_config()
        )
        self._config_pages["fecha"] = self._config_stack.addWidget(
            self._make_date_config()
        )
        self._config_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        form.addRow(self.tr("Configuración:"), self._config_stack)
        return detail

    def _make_text_config(self) -> QWidget:
        lbl = QLabel(self.tr("Sin configuración adicional"))
        lbl.setObjectName("hint_label")
        return lbl

    def _make_list_config(self) -> QWidget:
        """Tipo lista: valores separados por coma."""
        self._list_values = QLineEdit()
        self._list_values.setObjectName("listValues")
        self._list_values.setPlaceholderText(self.tr("valor1, valor2, valor3..."))
        self._list_values.textChanged.connect(self._store_current)
        return self._list_values

    def _make_numeric_config(self) -> QWidget:
        """Tipo numérico: min, max, step (enteros)."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._num_min = QSpinBox()
        self._num_min.setObjectName("numMin")
        self._num_min.setRange(-999999, 999999)
        self._num_max = QSpinBox()
        self._num_max.setObjectName("numMax")
        self._num_max.setRange(-999999, 999999)
        self._num_step = QSpinBox()
        self._num_step.setObjectName("numStep")
        self._num_step.setRange(1, 999999)
        for label, spin in (
            (self.tr("Mín:"), self._num_min),
            (self.tr("Máx:"), self._num_max),
            (self.tr("Paso:"), self._num_step),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(spin)
            spin.valueChanged.connect(self._store_current)
        layout.addStretch(1)
        return container

    def _make_date_config(self) -> QWidget:
        """Tipo fecha: formato de la fecha."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(self.tr("Formato:")))
        self._date_format = QComboBox()
        self._date_format.setObjectName("dateFormat")
        self._date_format.addItems(DATE_FORMATS)
        self._date_format.currentTextChanged.connect(self._store_current)
        layout.addWidget(self._date_format)
        layout.addStretch(1)
        return container

    # ------------------------------------------------------------------
    # Lista
    # ------------------------------------------------------------------

    def _load_fields(self, app: Application) -> None:
        """Carga los campos desde batch_fields_json."""
        try:
            fields = json.loads(app.batch_fields_json or "[]")
        except json.JSONDecodeError, TypeError:
            fields = []
        self._fields = [copy.deepcopy(f) for f in fields if isinstance(f, dict)]
        self._rebuild_list(0 if self._fields else -1)

    def _rebuild_list(self, select: int) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for field in self._fields:
            item = QListWidgetItem()
            row = _FieldRow()
            row.set_field(field)
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        self._list.blockSignals(False)
        self._current = -1
        if 0 <= select < len(self._fields):
            self._list.setCurrentRow(select)
        else:
            self._on_row_changed(-1)

    def _refresh_row(self, index: int) -> None:
        item = self._list.item(index)
        if item is None:
            return
        row = self._list.itemWidget(item)
        if isinstance(row, _FieldRow):
            row.set_field(self._fields[index])

    def field_count(self) -> int:
        return len(self._fields)

    def _add_empty_row(self) -> None:
        """Añade un campo vacío y lo selecciona para completarlo."""
        self._fields.append({"label": "", "type": "texto", "required": False})
        self._rebuild_list(len(self._fields) - 1)
        self._label_edit.setFocus()

    def _remove_row(self, row: int) -> None:
        """Elimina un campo."""
        if row < 0 or row >= len(self._fields):
            return
        del self._fields[row]
        self._rebuild_list(min(row, len(self._fields) - 1))

    def _move_row(self, row: int, direction: int) -> None:
        """Mueve un campo arriba (-1) o abajo (+1)."""
        target = row + direction
        if row < 0 or target < 0 or target >= len(self._fields):
            return
        self._fields[row], self._fields[target] = (
            self._fields[target],
            self._fields[row],
        )
        self._rebuild_list(target)

    # ------------------------------------------------------------------
    # Detalle
    # ------------------------------------------------------------------

    def _on_row_changed(self, row: int) -> None:
        self._current = row if 0 <= row < len(self._fields) else -1
        has_field = self._current >= 0
        self._detail_stack.setCurrentIndex(1 if has_field else 0)
        for btn in (self._btn_remove, self._btn_up, self._btn_down):
            btn.setEnabled(has_field)
        if has_field:
            self._load_current()

    def _load_current(self) -> None:
        field = self._fields[self._current]
        config = field.get("config") or {}
        self._loading = True
        try:
            self._label_edit.setText(str(field.get("label", "")))
            field_type = field.get("type", "texto")
            idx = self._type_combo.findText(field_type)
            self._type_combo.setCurrentIndex(max(idx, 0))
            self._show_config_page(self._type_combo.currentText())
            self._required_check.setChecked(bool(field.get("required", False)))
            self._default_edit.setText(str(field.get("default", "") or ""))
            self._description_edit.setPlainText(str(field.get("description", "") or ""))
            self._list_values.setText(", ".join(config.get("values", []) or []))
            self._num_min.setValue(int(config.get("min", 0)))
            self._num_max.setValue(int(config.get("max", 100)))
            self._num_step.setValue(int(config.get("step", 1)))
            fmt_idx = self._date_format.findText(config.get("format", "dd/MM/yyyy"))
            self._date_format.setCurrentIndex(max(fmt_idx, 0))
        finally:
            self._loading = False

    def _show_config_page(self, field_type: str) -> None:
        self._config_stack.setCurrentIndex(
            self._config_pages.get(field_type, self._config_pages["texto"])
        )

    def _on_type_changed(self, new_type: str) -> None:
        self._show_config_page(new_type)
        self._store_current()

    def _typed_config(self, field_type: str) -> dict[str, Any]:
        """Configuración del tipo según los controles del editor."""
        if field_type == "lista":
            raw = self._list_values.text().strip()
            values = [v.strip() for v in raw.split(",") if v.strip()] if raw else []
            return {"values": values}
        if field_type == "numérico":
            return {
                "min": self._num_min.value(),
                "max": self._num_max.value(),
                "step": self._num_step.value(),
            }
        if field_type == "fecha":
            return {"format": self._date_format.currentText()}
        return {}

    def _store_current(self, *_args) -> None:
        """Vuelca el editor sobre el campo seleccionado."""
        if self._loading or self._current < 0:
            return
        field = self._fields[self._current]
        field["label"] = self._label_edit.text()
        field_type = self._type_combo.currentText()
        field["type"] = field_type
        field["required"] = self._required_check.isChecked()
        for key, value in (
            ("default", self._default_edit.text()),
            ("description", self._description_edit.toPlainText()),
        ):
            if value.strip():
                field[key] = value
            else:
                field.pop(key, None)

        old_config = field.get("config") or {}
        config = {k: v for k, v in old_config.items() if k not in _ALL_TYPED_KEYS}
        config.update(self._typed_config(field_type))
        if config:
            field["config"] = config
        else:
            field.pop("config", None)
        self._refresh_row(self._current)

    # ------------------------------------------------------------------
    # Guardado
    # ------------------------------------------------------------------

    def apply_to(self, app: Application) -> None:
        """Serializa los campos a Application.batch_fields_json."""
        fields: list[dict[str, Any]] = []
        for field in self._fields:
            label = str(field.get("label", "")).strip()
            if not label:
                continue  # Saltar campos sin nombre
            out = dict(field)
            out["label"] = label
            fields.append(out)

        app.batch_fields_json = json.dumps(fields, ensure_ascii=False)
        log.info("Campos de lote guardados: %d campos", len(fields))
