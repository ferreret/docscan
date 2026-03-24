"""Widget de lista de lotes con colores por estado."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Qt, Signal
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

_STATE_LABELS_SRC: dict[str, str] = {
    "created": QT_TRANSLATE_NOOP("BatchListWidget", "Creado"),
    "read": QT_TRANSLATE_NOOP("BatchListWidget", "Leído"),
    "verified": QT_TRANSLATE_NOOP("BatchListWidget", "Verificado"),
    "ready_to_export": QT_TRANSLATE_NOOP("BatchListWidget", "Listo exportar"),
    "exported": QT_TRANSLATE_NOOP("BatchListWidget", "Exportado"),
    "error_read": QT_TRANSLATE_NOOP("BatchListWidget", "Error lectura"),
    "error_export": QT_TRANSLATE_NOOP("BatchListWidget", "Error export."),
}

_COLUMNS_SRC = [
    QT_TRANSLATE_NOOP("BatchListWidget", "ID"),
    QT_TRANSLATE_NOOP("BatchListWidget", "Aplicación"),
    QT_TRANSLATE_NOOP("BatchListWidget", "Páginas"),
    QT_TRANSLATE_NOOP("BatchListWidget", "Estación"),
    QT_TRANSLATE_NOOP("BatchListWidget", "Creado"),
    QT_TRANSLATE_NOOP("BatchListWidget", "Actualizado"),
]


def STATE_LABELS() -> dict[str, str]:
    """Devuelve etiquetas de estado traducidas (evaluadas en tiempo de uso)."""
    _t = lambda s: QCoreApplication.translate("BatchListWidget", s)
    return {k: _t(v) for k, v in _STATE_LABELS_SRC.items()}


def COLUMNS() -> list[str]:
    """Devuelve cabeceras de columna traducidas (evaluadas en tiempo de uso)."""
    _t = lambda s: QCoreApplication.translate("BatchListWidget", s)
    return [_t(s) for s in _COLUMNS_SRC]


class BatchListWidget(QTableWidget):
    """Tabla de lotes.

    Signals:
        batch_selected: Emitida al seleccionar un lote (batch_id).
        batch_double_clicked: Emitida al hacer doble click en un lote.
    """

    batch_selected = Signal(int)
    batch_double_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._batch_ids: list[int] = []
        self._theme_manager = ThemeManager()
        self._setup_table()

    def _setup_table(self) -> None:
        """Configura la tabla."""
        cols = COLUMNS()
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)
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

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.cellDoubleClicked.connect(self._on_double_click)

    def set_batches(self, batches: list[dict[str, Any]]) -> None:
        """Carga la lista de lotes."""
        self.blockSignals(True)
        try:
            self._set_batches_inner(batches)
        finally:
            self.blockSignals(False)

    def _set_batches_inner(self, batches: list[dict[str, Any]]) -> None:
        """Carga interna sin señales."""
        self.setRowCount(0)
        self._batch_ids.clear()

        is_dark = self._theme_manager.is_dark
        theme_idx = 0 if is_dark else 1

        for row_idx, batch in enumerate(batches):
            self.insertRow(row_idx)
            self._batch_ids.append(batch["id"])

            state = batch.get("state", "created")
            # Fondo sutil para la fila según estado
            state_bg = QColor(
                STATE_COLORS_THEMED.get(state, ("#313244", "#FFFFFF"))[theme_idx]
            )
            state_bg.setAlpha(40 if is_dark else 60)

            items = [
                str(batch["id"]),
                batch.get("app_name", ""),
                str(batch.get("page_count", 0)),
                batch.get("hostname", ""),
                self._format_datetime(batch.get("created_at")),
                self._format_datetime(batch.get("updated_at")),
            ]

            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setBackground(QBrush(state_bg))

                if col_idx in (0, 2):  # ID y Páginas centrados
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

    def _on_double_click(self, row: int, _col: int) -> None:
        """Emite señal de doble click para abrir el lote."""
        if 0 <= row < len(self._batch_ids):
            self.batch_double_clicked.emit(self._batch_ids[row])

    @staticmethod
    def _format_datetime(dt: datetime | str | None) -> str:
        """Formatea datetime para mostrar."""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.strftime("%d/%m/%Y %H:%M")
