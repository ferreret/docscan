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

from app.ui.theme_manager import ThemeManager

log = logging.getLogger(__name__)

# Colores por estado: (dark, light)
STATE_COLORS_THEMED: dict[str, tuple[str, str]] = {
    "created":         ("#585b70", "#E0E0E0"),
    "read":            ("#3b5998", "#BBDEFB"),
    "verified":        ("#2e7d32", "#C8E6C9"),
    "ready_to_export": ("#8d6e00", "#FFF9C4"),
    "exported":        ("#1b5e20", "#A5D6A7"),
    "error_read":      ("#b71c1c", "#FFCDD2"),
    "error_export":    ("#c62828", "#EF9A9A"),
}

# Colores de texto para estado (dark, light)
STATE_TEXT_COLORS: dict[str, tuple[str, str]] = {
    "created":         ("#a6adc8", "#666666"),
    "read":            ("#89b4fa", "#1565C0"),
    "verified":        ("#a6e3a1", "#2E7D32"),
    "ready_to_export": ("#f9e2af", "#F57F17"),
    "exported":        ("#a6e3a1", "#1B5E20"),
    "error_read":      ("#f38ba8", "#C62828"),
    "error_export":    ("#f38ba8", "#B71C1C"),
}

STATE_LABELS: dict[str, str] = {
    "created": "Creado",
    "read": "Le\u00eddo",
    "verified": "Verificado",
    "ready_to_export": "Listo exportar",
    "exported": "Exportado",
    "error_read": "Error lectura",
    "error_export": "Error export.",
}

COLUMNS = ["ID", "Aplicaci\u00f3n", "Estado", "P\u00e1ginas", "Estaci\u00f3n", "Creado", "Actualizado"]


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
        self.setShowGrid(False)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_batches(self, batches: list[dict[str, Any]]) -> None:
        """Carga la lista de lotes."""
        self.setRowCount(0)
        self._batch_ids.clear()

        is_dark = ThemeManager().is_dark
        theme_idx = 0 if is_dark else 1

        for row_idx, batch in enumerate(batches):
            self.insertRow(row_idx)
            self._batch_ids.append(batch["id"])

            state = batch.get("state", "created")
            state_text_color = QColor(
                STATE_TEXT_COLORS.get(state, ("#cdd6f4", "#4c4f69"))[theme_idx]
            )
            # Fondo sutil para la fila según estado
            state_bg = QColor(
                STATE_COLORS_THEMED.get(state, ("#313244", "#FFFFFF"))[theme_idx]
            )
            state_bg.setAlpha(40 if is_dark else 60)

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
                item.setBackground(QBrush(state_bg))

                if col_idx == 2:  # Columna Estado: texto coloreado
                    item.setForeground(QBrush(state_text_color))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

                if col_idx in (0, 3):  # ID y Páginas centrados
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

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
