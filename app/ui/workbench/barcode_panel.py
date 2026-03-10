"""Panel de barcodes de la página actual (UI-08).

Muestra lista de barcodes con valor, simbología, motor y rol.
Incluye contadores del lote y opción de copiar al portapapeles.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)


class BarcodePanel(QWidget):
    """Panel derecho superior: barcodes y contadores."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Tabla de barcodes
        group = QGroupBox("Barcodes de la página")
        group_layout = QVBoxLayout(group)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Valor", "Simbología", "Motor", "Rol"],
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(100)
        header.resizeSection(0, 200)  # Valor más ancho por defecto
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        group_layout.addWidget(self._table)
        layout.addWidget(group)

        # Contadores del lote
        counters_group = QGroupBox("Contadores del lote")
        counters_layout = QVBoxLayout(counters_group)

        self._lbl_total = QLabel("Total páginas: 0")
        self._lbl_with_barcode = QLabel("Con barcode: 0")
        self._lbl_separators = QLabel("Separadores: 0")
        self._lbl_review = QLabel("Revisión: 0")

        counters_layout.addWidget(self._lbl_total)
        counters_layout.addWidget(self._lbl_with_barcode)
        counters_layout.addWidget(self._lbl_separators)
        counters_layout.addWidget(self._lbl_review)
        layout.addWidget(counters_group)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_page_barcodes(self, barcodes: list) -> None:
        """Muestra los barcodes de la página actual."""
        self._table.setRowCount(0)
        for bc in barcodes:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(
                row, 0,
                QTableWidgetItem(getattr(bc, "value", str(bc))),
            )
            self._table.setItem(
                row, 1, QTableWidgetItem(getattr(bc, "symbology", "")),
            )
            self._table.setItem(
                row, 2, QTableWidgetItem(getattr(bc, "engine", "")),
            )
            self._table.setItem(
                row, 3, QTableWidgetItem(getattr(bc, "role", "")),
            )

    def set_lot_counters(self, stats: dict) -> None:
        """Actualiza los contadores del lote."""
        self._lbl_total.setText(
            f"Total páginas: {stats.get('total_pages', 0)}"
        )
        self._lbl_with_barcode.setText(
            f"Con barcode: {stats.get('with_barcode', 0)}"
        )
        self._lbl_separators.setText(
            f"Separadores: {stats.get('separators', 0)}"
        )
        self._lbl_review.setText(
            f"Revisión: {stats.get('needs_review', 0)}"
        )

    def clear(self) -> None:
        """Limpia tabla y contadores."""
        self._table.setRowCount(0)
        self._lbl_total.setText("Total páginas: 0")
        self._lbl_with_barcode.setText("Con barcode: 0")
        self._lbl_separators.setText("Separadores: 0")
        self._lbl_review.setText("Revisión: 0")

    # ------------------------------------------------------------------
    # Menú contextual
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Menú contextual: copiar valor / copiar todos."""
        menu = QMenu(self)
        act_copy = menu.addAction("Copiar valor")
        act_copy_all = menu.addAction("Copiar todos")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        clipboard = QApplication.clipboard()

        if action == act_copy:
            row = self._table.currentRow()
            if row >= 0:
                item = self._table.item(row, 0)
                if item:
                    clipboard.setText(item.text())
        elif action == act_copy_all:
            values = []
            for r in range(self._table.rowCount()):
                item = self._table.item(r, 0)
                if item:
                    values.append(item.text())
            clipboard.setText("\n".join(values))
