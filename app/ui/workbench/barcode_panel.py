"""Panel de barcodes de la página actual (UI-08).

Muestra lista de barcodes con valor, simbología, motor y rol.
Incluye contadores del lote y opción de copiar al portapapeles.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.workbench.document_viewer import _BARCODE_PALETTE

log = logging.getLogger(__name__)

_DOT_RADIUS = 6


class _ColorDotDelegate(QStyledItemDelegate):
    """Pinta un círculo de color en la celda usando el UserRole data."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color_hex = index.data(Qt.ItemDataRole.UserRole)
        if color_hex:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color_hex))
            center = QPoint(
                option.rect.center().x(),
                option.rect.center().y(),
            )
            painter.drawEllipse(center, _DOT_RADIUS, _DOT_RADIUS)
        painter.restore()


class BarcodePanel(QWidget):
    """Panel derecho superior: barcodes y contadores.

    Signals:
        insert_barcode_requested: Solicita añadir barcode manual.
        delete_barcode_requested: Solicita eliminar barcode seleccionado.
    """

    insert_barcode_requested = Signal()
    delete_barcode_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Tabla de barcodes
        group = QGroupBox(self.tr("Barcodes de la p\u00e1gina"))
        group_layout = QVBoxLayout(group)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["", self.tr("Valor"), self.tr("Simbolog\u00eda"), self.tr("Motor"), self.tr("Rol")],
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(100)
        header.resizeSection(0, 28)   # Columna de color (estrecha)
        header.resizeSection(1, 180)  # Valor
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.setItemDelegateForColumn(0, _ColorDotDelegate(self._table))

        group_layout.addWidget(self._table)

        # Botones de barcode
        bc_buttons = QHBoxLayout()
        self._btn_insert_bc = QPushButton(self.tr("+ Barcode manual"))
        self._btn_delete_bc = QPushButton(self.tr("\u2212 Barcode"))
        self._btn_insert_bc.clicked.connect(self.insert_barcode_requested)
        self._btn_delete_bc.clicked.connect(self.delete_barcode_requested)
        bc_buttons.addWidget(self._btn_insert_bc)
        bc_buttons.addWidget(self._btn_delete_bc)
        group_layout.addLayout(bc_buttons)

        layout.addWidget(group)

        # Contadores del lote
        counters_group = QGroupBox(self.tr("Contadores del lote"))
        counters_layout = QVBoxLayout(counters_group)

        self._lbl_total = QLabel(self.tr("Total p\u00e1ginas: {0}").format(0))
        self._lbl_with_barcode = QLabel(self.tr("Con barcode: {0}").format(0))
        self._lbl_separators = QLabel(self.tr("Separadores: {0}").format(0))
        self._lbl_review = QLabel(self.tr("Revisi\u00f3n: {0}").format(0))

        counters_layout.addWidget(self._lbl_total)
        counters_layout.addWidget(self._lbl_with_barcode)
        counters_layout.addWidget(self._lbl_separators)
        counters_layout.addWidget(self._lbl_review)
        layout.addWidget(counters_group)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_page_barcodes(self, barcodes: list) -> None:
        """Muestra los barcodes de la página actual con indicador de color."""
        self._table.setRowCount(0)
        for idx, bc in enumerate(barcodes):
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Columna 0: círculo de color (mismo que el overlay del visor)
            pen_hex, _fill_hex = _BARCODE_PALETTE[idx % len(_BARCODE_PALETTE)]
            color_item = QTableWidgetItem()
            color_item.setData(Qt.ItemDataRole.UserRole, pen_hex)
            color_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(row, 0, color_item)

            self._table.setItem(
                row, 1,
                QTableWidgetItem(getattr(bc, "value", str(bc))),
            )
            self._table.setItem(
                row, 2, QTableWidgetItem(getattr(bc, "symbology", "")),
            )
            self._table.setItem(
                row, 3, QTableWidgetItem(getattr(bc, "engine", "")),
            )
            self._table.setItem(
                row, 4, QTableWidgetItem(getattr(bc, "role", "")),
            )

    def set_lot_counters(self, stats: dict) -> None:
        """Actualiza los contadores del lote."""
        self._lbl_total.setText(
            self.tr("Total p\u00e1ginas: {0}").format(stats.get('total_pages', 0))
        )
        self._lbl_with_barcode.setText(
            self.tr("Con barcode: {0}").format(stats.get('with_barcode', 0))
        )
        self._lbl_separators.setText(
            self.tr("Separadores: {0}").format(stats.get('separators', 0))
        )
        self._lbl_review.setText(
            self.tr("Revisi\u00f3n: {0}").format(stats.get('needs_review', 0))
        )

    def selected_row(self) -> int:
        """Devuelve el índice de la fila seleccionada, o -1."""
        return self._table.currentRow()

    def selected_value(self) -> str:
        """Devuelve el valor del barcode seleccionado, o cadena vacía."""
        row = self._table.currentRow()
        if row < 0:
            return ""
        item = self._table.item(row, 1)
        return item.text() if item else ""

    def clear(self) -> None:
        """Limpia tabla y contadores."""
        self._table.setRowCount(0)
        self._lbl_total.setText(self.tr("Total p\u00e1ginas: {0}").format(0))
        self._lbl_with_barcode.setText(self.tr("Con barcode: {0}").format(0))
        self._lbl_separators.setText(self.tr("Separadores: {0}").format(0))
        self._lbl_review.setText(self.tr("Revisi\u00f3n: {0}").format(0))

    # ------------------------------------------------------------------
    # Menú contextual
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Menú contextual: copiar valor / copiar todos."""
        menu = QMenu(self)
        act_copy = menu.addAction(self.tr("Copiar valor"))
        act_copy_all = menu.addAction(self.tr("Copiar todos"))

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        clipboard = QApplication.clipboard()

        if action == act_copy:
            row = self._table.currentRow()
            if row >= 0:
                item = self._table.item(row, 1)
                if item:
                    clipboard.setText(item.text())
        elif action == act_copy_all:
            values = []
            for r in range(self._table.rowCount()):
                item = self._table.item(r, 1)
                if item:
                    values.append(item.text())
            clipboard.setText("\n".join(values))
