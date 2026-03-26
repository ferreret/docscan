"""Pestaña de Campos de Lote del configurador.

Permite definir N campos dinámicos por aplicación. Cada campo tiene:
- Label (nombre visible)
- Tipo: texto, lista predefinida, numérico (min/max/step)
- Obligatorio (sí/no)

Los campos se serializan en Application.batch_fields_json.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application

log = logging.getLogger(__name__)

# Tipos de campo disponibles
FIELD_TYPES = ["texto", "fecha", "lista", "numérico"]

# Columnas de la tabla
_COL_LABEL = 0
_COL_TYPE = 1
_COL_CONFIG = 2
_COL_REQUIRED = 3
_COL_ACTIONS = 4
_COLUMN_HEADERS_SRC = [
    QT_TRANSLATE_NOOP("BatchFieldsTab", "Etiqueta"),
    QT_TRANSLATE_NOOP("BatchFieldsTab", "Tipo"),
    QT_TRANSLATE_NOOP("BatchFieldsTab", "Configuración"),
    QT_TRANSLATE_NOOP("BatchFieldsTab", "Obligatorio"),
    "",
]


def _column_headers() -> list[str]:
    """Devuelve cabeceras traducidas."""
    _t = lambda s: QCoreApplication.translate("BatchFieldsTab", s) if s else ""
    return [_t(s) for s in _COLUMN_HEADERS_SRC]


class BatchFieldsTab(QWidget):
    """Pestaña para definir campos de lote dinámicos."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_fields(app)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton(self.tr("+ Añadir campo"))
        btn_add.setToolTip(self.tr("Añadir un nuevo campo de lote a la aplicación"))
        btn_add.clicked.connect(self._add_empty_row)
        toolbar.addWidget(btn_add)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tabla
        self._table = QTableWidget(0, len(_COLUMN_HEADERS_SRC))
        self._table.setHorizontalHeaderLabels(_column_headers())
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(48)
        self._table.verticalHeader().setMinimumSectionSize(48)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_TYPE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_TYPE, 120)
        header.setSectionResizeMode(_COL_CONFIG, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _COL_REQUIRED, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            _COL_ACTIONS, QHeaderView.ResizeMode.ResizeToContents
        )
        # Mínimos para que no se compriman demasiado
        header.setMinimumSectionSize(50)

        layout.addWidget(self._table)

    def _load_fields(self, app: Application) -> None:
        """Carga los campos desde batch_fields_json."""
        try:
            fields = json.loads(app.batch_fields_json or "[]")
        except (json.JSONDecodeError, TypeError):
            fields = []

        for field in fields:
            self._add_row(field)

    def _add_empty_row(self) -> None:
        """Añade una fila vacía con valores por defecto."""
        self._add_row({"label": "", "type": "texto", "required": False})

    @staticmethod
    def _wrap_centered(widget: QWidget) -> QWidget:
        """Envuelve un widget en un contenedor con margen uniforme."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.addWidget(widget)
        return container

    def _add_row(self, field: dict[str, Any]) -> None:
        """Añade una fila con los datos del campo."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Etiqueta
        label_edit = QLineEdit(field.get("label", ""))
        label_edit.setPlaceholderText(self.tr("Nombre del campo..."))
        label_edit.setToolTip(self.tr("Nombre del campo que aparecerá como etiqueta en el workbench"))
        self._table.setCellWidget(row, _COL_LABEL, self._wrap_centered(label_edit))

        # Tipo
        type_combo = QComboBox()
        type_combo.setMinimumWidth(100)
        type_combo.setToolTip(self.tr("Tipo de dato: texto, fecha, lista desplegable o numérico"))
        type_combo.addItems(FIELD_TYPES)
        field_type = field.get("type", "texto")
        idx = type_combo.findText(field_type)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        self._table.setCellWidget(row, _COL_TYPE, self._wrap_centered(type_combo))

        # Configuración (depende del tipo)
        config_widget = self._make_config_widget(field_type, field.get("config"))
        self._table.setCellWidget(row, _COL_CONFIG, config_widget)

        # Reconectar: al cambiar tipo, reemplazar widget de config
        type_combo.currentTextChanged.connect(
            lambda new_type, r=row: self._on_type_changed(r, new_type)
        )

        # Obligatorio
        required_container = QWidget()
        req_layout = QHBoxLayout(required_container)
        req_layout.setContentsMargins(0, 0, 0, 0)
        req_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        required_check = QCheckBox()
        required_check.setToolTip(self.tr("Marcar si este campo es obligatorio antes de transferir"))
        required_check.setChecked(field.get("required", False))
        req_layout.addWidget(required_check)
        self._table.setCellWidget(row, _COL_REQUIRED, required_container)

        # Acciones: subir, bajar, eliminar
        actions = QWidget()
        act_layout = QHBoxLayout(actions)
        act_layout.setContentsMargins(2, 0, 2, 0)
        act_layout.setSpacing(2)

        btn_up = QPushButton("▲")
        btn_up.setFixedWidth(26)
        btn_up.setToolTip(self.tr("Subir"))
        btn_up.clicked.connect(lambda _, r=row: self._move_row(r, -1))

        btn_down = QPushButton("▼")
        btn_down.setFixedWidth(26)
        btn_down.setToolTip(self.tr("Bajar"))
        btn_down.clicked.connect(lambda _, r=row: self._move_row(r, 1))

        btn_del = QPushButton("✕")
        btn_del.setFixedWidth(26)
        btn_del.setToolTip(self.tr("Eliminar"))
        btn_del.clicked.connect(lambda _, r=row: self._remove_row(r))

        act_layout.addWidget(btn_up)
        act_layout.addWidget(btn_down)
        act_layout.addWidget(btn_del)
        self._table.setCellWidget(row, _COL_ACTIONS, actions)

    def _make_config_widget(
        self, field_type: str, config: dict[str, Any] | None = None
    ) -> QWidget:
        """Crea el widget de configuración según el tipo de campo."""
        config = config or {}

        if field_type == "lista":
            return self._make_list_config(config)
        elif field_type == "numérico":
            return self._make_numeric_config(config)
        elif field_type == "fecha":
            return self._make_date_config(config)
        else:
            # Texto: sin configuración adicional
            placeholder = QWidget()
            lbl_layout = QHBoxLayout(placeholder)
            lbl_layout.setContentsMargins(4, 0, 4, 0)
            lbl = QLabel(self.tr("Sin configuración adicional"))
            lbl.setStyleSheet("color: gray; font-style: italic;")
            lbl_layout.addWidget(lbl)
            return placeholder

    def _make_list_config(self, config: dict[str, Any]) -> QWidget:
        """Widget para tipo lista: campo de texto con valores separados por coma."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)

        lbl = QLabel(self.tr("Valores:"))
        layout.addWidget(lbl)

        values_edit = QLineEdit()
        values_edit.setObjectName("listValues")
        values_edit.setPlaceholderText(self.tr("valor1, valor2, valor3..."))
        values = config.get("values", [])
        if values:
            values_edit.setText(", ".join(values))
        layout.addWidget(values_edit)

        return container

    def _make_numeric_config(self, config: dict[str, Any]) -> QWidget:
        """Widget para tipo numérico: min, max, step (enteros)."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        lbl_min = QLabel(self.tr("Mín:"))
        spin_min = QSpinBox()
        spin_min.setObjectName("numMin")
        spin_min.setRange(-999999, 999999)
        spin_min.setValue(int(config.get("min", 0)))

        lbl_max = QLabel(self.tr("Máx:"))
        spin_max = QSpinBox()
        spin_max.setObjectName("numMax")
        spin_max.setRange(-999999, 999999)
        spin_max.setValue(int(config.get("max", 100)))

        lbl_step = QLabel(self.tr("Paso:"))
        spin_step = QSpinBox()
        spin_step.setObjectName("numStep")
        spin_step.setRange(1, 999999)
        spin_step.setValue(int(config.get("step", 1)))

        for w in (lbl_min, spin_min, lbl_max, spin_max, lbl_step, spin_step):
            layout.addWidget(w)

        return container

    def _make_date_config(self, config: dict[str, Any]) -> QWidget:
        """Widget para tipo fecha: selector de formato."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)

        lbl = QLabel(self.tr("Formato:"))
        layout.addWidget(lbl)

        fmt_combo = QComboBox()
        fmt_combo.setObjectName("dateFormat")
        fmt_combo.addItems(["dd/MM/yyyy", "yyyy-MM-dd", "dd-MM-yyyy", "MM/dd/yyyy"])
        saved_fmt = config.get("format", "dd/MM/yyyy")
        idx = fmt_combo.findText(saved_fmt)
        if idx >= 0:
            fmt_combo.setCurrentIndex(idx)
        layout.addWidget(fmt_combo)

        return container

    def _on_type_changed(self, row: int, new_type: str) -> None:
        """Reemplaza el widget de configuración al cambiar el tipo."""
        old_widget = self._table.cellWidget(row, _COL_CONFIG)
        config = self._extract_config_from_widget(old_widget) if old_widget else {}
        new_widget = self._make_config_widget(new_type, config if new_type != "texto" else None)
        self._table.setCellWidget(row, _COL_CONFIG, new_widget)

    def _move_row(self, row: int, direction: int) -> None:
        """Mueve una fila arriba (-1) o abajo (+1)."""
        target = row + direction
        if target < 0 or target >= self._table.rowCount():
            return

        # Extraer datos de ambas filas
        data_row = self._extract_row_data(row)
        data_target = self._extract_row_data(target)

        # Reescribir intercambiadas
        self._set_row_data(row, data_target)
        self._set_row_data(target, data_row)

        self._table.selectRow(target)

    def _remove_row(self, row: int) -> None:
        """Elimina una fila."""
        if row < 0 or row >= self._table.rowCount():
            return
        self._table.removeRow(row)
        # Reconectar lambdas de filas posteriores
        self._reconnect_actions()

    def _reconnect_actions(self) -> None:
        """Reconstruye las conexiones de botones tras eliminar/mover filas.

        Las lambdas capturan el índice de fila en el momento de la creación,
        así que tras eliminar una fila hay que reconectar.
        """
        for row in range(self._table.rowCount()):
            # Recrear acciones
            data = self._extract_row_data(row)
            self._set_row_data(row, data)

    def _extract_row_data(self, row: int) -> dict[str, Any]:
        """Extrae todos los datos de una fila como dict."""
        label_container = self._table.cellWidget(row, _COL_LABEL)
        label_w = label_container.findChild(QLineEdit) if label_container else None
        label = label_w.text() if label_w else ""

        type_container = self._table.cellWidget(row, _COL_TYPE)
        type_w = type_container.findChild(QComboBox) if type_container else None
        field_type = type_w.currentText() if type_w else "texto"

        config_w = self._table.cellWidget(row, _COL_CONFIG)
        config = self._extract_config_from_widget(config_w)

        req_container = self._table.cellWidget(row, _COL_REQUIRED)
        required = False
        if req_container:
            cb = req_container.findChild(QCheckBox)
            if cb:
                required = cb.isChecked()

        return {
            "label": label,
            "type": field_type,
            "config": config,
            "required": required,
        }

    def _set_row_data(self, row: int, data: dict[str, Any]) -> None:
        """Reescribe una fila completa con los datos proporcionados."""
        # Remover fila actual y reinsertar
        self._table.removeRow(row)
        self._table.insertRow(row)

        # Etiqueta
        label_edit = QLineEdit(data.get("label", ""))
        label_edit.setPlaceholderText(self.tr("Nombre del campo..."))
        self._table.setCellWidget(row, _COL_LABEL, self._wrap_centered(label_edit))

        # Tipo
        type_combo = QComboBox()
        type_combo.setMinimumWidth(100)
        type_combo.addItems(FIELD_TYPES)
        field_type = data.get("type", "texto")
        idx = type_combo.findText(field_type)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        self._table.setCellWidget(row, _COL_TYPE, self._wrap_centered(type_combo))

        # Config
        config_widget = self._make_config_widget(field_type, data.get("config"))
        self._table.setCellWidget(row, _COL_CONFIG, config_widget)

        type_combo.currentTextChanged.connect(
            lambda new_type, r=row: self._on_type_changed(r, new_type)
        )

        # Obligatorio
        required_container = QWidget()
        req_layout = QHBoxLayout(required_container)
        req_layout.setContentsMargins(0, 0, 0, 0)
        req_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        required_check = QCheckBox()
        required_check.setChecked(data.get("required", False))
        req_layout.addWidget(required_check)
        self._table.setCellWidget(row, _COL_REQUIRED, required_container)

        # Acciones
        actions = QWidget()
        act_layout = QHBoxLayout(actions)
        act_layout.setContentsMargins(2, 0, 2, 0)
        act_layout.setSpacing(2)

        btn_up = QPushButton("▲")
        btn_up.setFixedWidth(26)
        btn_up.setToolTip(self.tr("Subir"))
        btn_up.clicked.connect(lambda _, r=row: self._move_row(r, -1))

        btn_down = QPushButton("▼")
        btn_down.setFixedWidth(26)
        btn_down.setToolTip(self.tr("Bajar"))
        btn_down.clicked.connect(lambda _, r=row: self._move_row(r, 1))

        btn_del = QPushButton("✕")
        btn_del.setFixedWidth(26)
        btn_del.setToolTip(self.tr("Eliminar"))
        btn_del.clicked.connect(lambda _, r=row: self._remove_row(r))

        act_layout.addWidget(btn_up)
        act_layout.addWidget(btn_down)
        act_layout.addWidget(btn_del)
        self._table.setCellWidget(row, _COL_ACTIONS, actions)

    def _extract_config_from_widget(self, widget: QWidget | None) -> dict[str, Any]:
        """Extrae la configuración del widget de config."""
        if not widget:
            return {}

        # Lista
        values_edit = widget.findChild(QLineEdit, "listValues")
        if values_edit:
            raw = values_edit.text().strip()
            values = [v.strip() for v in raw.split(",") if v.strip()] if raw else []
            return {"values": values}

        # Numérico
        spin_min = widget.findChild(QSpinBox, "numMin")
        if spin_min:
            spin_max = widget.findChild(QSpinBox, "numMax")
            spin_step = widget.findChild(QSpinBox, "numStep")
            return {
                "min": spin_min.value(),
                "max": spin_max.value() if spin_max else 100,
                "step": spin_step.value() if spin_step else 1,
            }

        # Fecha
        fmt_combo = widget.findChild(QComboBox, "dateFormat")
        if fmt_combo:
            return {"format": fmt_combo.currentText()}

        return {}

    def apply_to(self, app: Application) -> None:
        """Serializa los campos de la tabla a Application.batch_fields_json."""
        fields: list[dict[str, Any]] = []

        for row in range(self._table.rowCount()):
            data = self._extract_row_data(row)
            label = data["label"].strip()
            if not label:
                continue  # Saltar filas sin etiqueta

            field: dict[str, Any] = {
                "label": label,
                "type": data["type"],
                "required": data["required"],
            }
            if data["config"]:
                field["config"] = data["config"]

            fields.append(field)

        app.batch_fields_json = json.dumps(fields, ensure_ascii=False)
        log.info("Campos de lote guardados: %d campos", len(fields))
