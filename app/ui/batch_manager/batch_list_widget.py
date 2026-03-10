"""Widget de lista de lotes con colores por estado (BAT-04)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

log = logging.getLogger(__name__)

# Colores por estado
STATE_COLORS: dict[str, str] = {
    "created": "#E0E0E0",       # Gris claro
    "read": "#BBDEFB",          # Azul claro
    "verified": "#C8E6C9",      # Verde claro
    "ready_to_export": "#FFF9C4",  # Amarillo claro
    "exported": "#A5D6A7",      # Verde
    "error_read": "#FFCDD2",    # Rojo claro
    "error_export": "#EF9A9A",  # Rojo
}

STATE_LABELS: dict[str, str] = {
    "created": "Creado",
    "read": "Leído",
    "verified": "Verificado",
    "ready_to_export": "Listo exportar",
    "exported": "Exportado",
    "error_read": "Error lectura",
    "error_export": "Error export.",
}

COLUMNS = ["ID", "Aplicación", "Estado", "Páginas", "Estación", "Creado", "Actualizado"]


class BatchListWidget(QTableWidget):
    """Tabla de lotes con colores por estado.

    Signals:
        batch_selected: Emitida al seleccionar un lote (batch_id).
    """

    batch_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._batch_ids: list[int] = []
        self._setup_table()

    def _setup_table(self) -> None:
        """Configura la tabla."""
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_batches(self, batches: list[dict[str, Any]]) -> None:
        """Carga la lista de lotes.

        Args:
            batches: Lista de dicts con keys: id, app_name, state,
                     page_count, hostname, created_at, updated_at.
        """
        self.setRowCount(0)
        self._batch_ids.clear()

        for row_idx, batch in enumerate(batches):
            self.insertRow(row_idx)
            self._batch_ids.append(batch["id"])

            state = batch.get("state", "created")
            color = QColor(STATE_COLORS.get(state, "#FFFFFF"))
            brush = QBrush(color)

            items = [
                str(batch["id"]),
                batch.get("app_name", ""),
                STATE_LABELS.get(state, state),
                str(batch.get("page_count", 0)),
                batch.get("hostname", ""),
                self._format_datetime(batch.get("created_at")),
                self._format_datetime(batch.get("updated_at")),
            ]

            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setBackground(brush)
                if col_idx in (0, 3):  # ID y Páginas centrados
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                self.setItem(row_idx, col_idx, item)

    def get_selected_batch_id(self) -> int | None:
        """Devuelve el ID del lote seleccionado o None."""
        row = self.currentRow()
        if 0 <= row < len(self._batch_ids):
            return self._batch_ids[row]
        return None

    def _on_selection_changed(self) -> None:
        """Emite la señal con el batch_id seleccionado."""
        batch_id = self.get_selected_batch_id()
        if batch_id is not None:
            self.batch_selected.emit(batch_id)

    @staticmethod
    def _format_datetime(dt: datetime | str | None) -> str:
        """Formatea datetime para mostrar."""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.strftime("%d/%m/%Y %H:%M")
