"""Panel «Barcodes de la página» del Workbench (UI-08).

Paridad con FlexibarNET 10: una fila por código —no una tabla— con punto de
color (el mismo que su recuadro en el visor), valor en monoespaciada,
«simbología · motor · rol» debajo, distintivo MANUAL para los añadidos a mano
y papelera por fila. Cabecera «BARCODES DE LA PÁGINA · N» con «+ Añadir» y
chevron de plegar; el cuerpo crece hasta 280 px y después hace scroll.

Pasar el ratón por una fila emite ``row_hovered`` para resaltar su recuadro
en el visor, y ``highlight_row`` hace lo contrario. Supr sobre una fila con
el foco la elimina (gana al atajo de ventana «borrar página»).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.palette import color
from app.ui.workbench.document_viewer import _BARCODE_PALETTE
from app.ui.workbench.section import CollapsibleSection

log = logging.getLogger(__name__)

# Tope de alto de la lista (como Flexibar): a partir de ahí, scroll interno.
BARCODES_MAX_HEIGHT = 280
MANUAL_ENGINE = "manual"


def barcode_color(index: int) -> str:
    """Color del código ``index``: el mismo que su recuadro en el visor."""
    return _BARCODE_PALETTE[index % len(_BARCODE_PALETTE)][0]


class _BarcodeRow(QFrame):
    """Fila de un código de barras."""

    hovered = Signal(int)  # índice, o -1 al salir
    clicked = Signal(int)
    delete_requested = Signal(int)
    context_requested = Signal(int, object)  # índice, posición global

    def __init__(self, index: int, barcode: Any, parent: QWidget | None = None):
        super().__init__(parent)
        self.index = index
        self.value = getattr(barcode, "value", str(barcode))
        self.barcode_id = getattr(barcode, "id", None)
        self.setObjectName("barcodeRow")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("highlighted", False)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        dot = QLabel()
        dot.setObjectName("barcodeDot")
        dot.setFixedSize(14, 14)
        dot.setStyleSheet(
            f"background-color: {barcode_color(index)}; border-radius: 7px;"
        )
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(2)
        self._lbl_value = QLabel()
        self._lbl_value.setObjectName("barcodeValue")
        self._lbl_value.setToolTip(self.value)
        self._lbl_value.setMinimumWidth(40)
        text.addWidget(self._lbl_value)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        engine = getattr(barcode, "engine", "") or ""
        parts = [getattr(barcode, "symbology", "") or ""]
        if engine and engine != MANUAL_ENGINE:
            parts.append(engine)
        role = getattr(barcode, "role", "") or ""
        meta_html = " · ".join(p for p in parts if p)
        if role:
            meta_html += f" · <span style='color:{color('blue')}'>{role}</span>"
        lbl_meta = QLabel(meta_html)
        lbl_meta.setObjectName("barcodeMeta")
        lbl_meta.setTextFormat(Qt.TextFormat.RichText)
        meta.addWidget(lbl_meta)
        if engine == MANUAL_ENGINE:
            badge = QLabel(self.tr("MANUAL"))
            badge.setObjectName("badgeManual")
            meta.addWidget(badge)
        meta.addStretch(1)
        text.addLayout(meta)
        layout.addLayout(text, 1)

        self._btn_delete = QPushButton()
        self._btn_delete.setObjectName("rowDeleteButton")
        self._btn_delete.setIcon(icon("trash-2", "red", 16))
        self._btn_delete.setIconSize(QSize(16, 16))
        self._btn_delete.setFixedSize(26, 24)
        self._btn_delete.setToolTip(self.tr("Eliminar este código (Supr)"))
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.index))
        layout.addWidget(self._btn_delete, 0, Qt.AlignmentFlag.AlignVCenter)

        self._elide_value()

    # -- presentación -----------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802 — API de Qt
        super().resizeEvent(event)
        self._elide_value()

    def _elide_value(self) -> None:
        width = max(40, self._lbl_value.width())
        metrics = QFontMetrics(self._lbl_value.font())
        self._lbl_value.setText(
            metrics.elidedText(self.value, Qt.TextElideMode.ElideRight, width)
        )

    def _set_flag(self, name: str, on: bool) -> None:
        if self.property(name) != on:
            self.setProperty(name, on)
            self.style().unpolish(self)
            self.style().polish(self)

    def set_highlighted(self, on: bool) -> None:
        self._set_flag("highlighted", on)

    def set_selected(self, on: bool) -> None:
        self._set_flag("selected", on)

    # -- eventos ------------------------------------------------------------

    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        self.hovered.emit(self.index)

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hovered.emit(-1)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.clicked.emit(self.index)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self.index)
        self.context_requested.emit(self.index, event.globalPos())

    def event(self, event) -> bool:
        # Supr con la fila enfocada borra el código, no la página: se
        # reclama la tecla antes de que llegue al atajo de la ventana.
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (
            Qt.Key.Key_Delete,
            Qt.Key.Key_Backspace,
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit(self.index)
            return
        super().keyPressEvent(event)


class BarcodePanel(QWidget):
    """Panel «Barcodes de la página».

    Signals:
        insert_barcode_requested: Pide añadir un código manual.
        delete_barcode_requested: Pide borrar el código de la fila (índice).
        row_hovered: Índice de la fila bajo el ratón, o -1.
    """

    insert_barcode_requested = Signal()
    delete_barcode_requested = Signal(int)
    row_hovered = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[_BarcodeRow] = []
        self._selected = -1
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QWidget()
        self._list.setObjectName("barcodeList")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(0)
        self._empty = QLabel(self.tr("Sin códigos en esta página"))
        self._empty.setObjectName("emptyHint")
        self._list_layout.addWidget(self._empty)

        self._section = CollapsibleSection(
            self.tr("Barcodes de la página"),
            self._list,
            max_body_height=BARCODES_MAX_HEIGHT,
        )
        self._btn_add = QPushButton(self.tr("+ Añadir"))
        self._btn_add.setObjectName("addBarcodeButton")
        self._btn_add.setToolTip(self.tr("Añadir un código a mano (Ctrl+N / Insert)"))
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.clicked.connect(self.insert_barcode_requested)
        self._section.add_header_widget(self._btn_add)
        layout.addWidget(self._section)
        self._section.fit_body()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_page_barcodes(self, barcodes: list) -> None:
        """Muestra los códigos de la página enfocada."""
        for row in self._rows:
            # Ocultar y soltar ya: deleteLater solo borra en la siguiente
            # vuelta del bucle y, mientras, la fila vieja se pintaba encima.
            self._list_layout.removeWidget(row)
            row.hide()
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        self._selected = -1
        for idx, bc in enumerate(barcodes):
            row = _BarcodeRow(idx, bc, self._list)
            row.hovered.connect(self.row_hovered)
            row.clicked.connect(self._select)
            row.delete_requested.connect(self.delete_barcode_requested)
            row.context_requested.connect(self._on_context_menu)
            self._list_layout.addWidget(row)
            # Visible ya: añadida a un panel que ya se ve, Qt la mostraría en
            # la siguiente vuelta del bucle y el layout no la mediría ahora.
            row.setVisible(True)
            self._rows.append(row)
        self._empty.setVisible(not self._rows)
        self._section.set_count(len(self._rows))
        self._section.fit_body()

    def row_count(self) -> int:
        return len(self._rows)

    def row_value(self, index: int) -> str:
        return self._rows[index].value if 0 <= index < len(self._rows) else ""

    def selected_row(self) -> int:
        """Índice de la fila seleccionada, o -1."""
        return self._selected

    def selected_value(self) -> str:
        """Valor de la fila seleccionada, o cadena vacía."""
        return self.row_value(self._selected)

    def highlight_row(self, index: int) -> None:
        """Resalta la fila ``index`` (-1 quita el resaltado)."""
        for row in self._rows:
            row.set_highlighted(row.index == index)

    def set_add_button_visible(self, visible: bool) -> None:
        """La aplicación puede ocultar «+ Añadir» (paridad Flexibar)."""
        self._btn_add.setVisible(visible)

    def refresh_icons(self) -> None:
        """Repinta los iconos con la paleta del tema activo."""
        self._section.refresh_icons()

    def clear(self) -> None:
        self.set_page_barcodes([])

    # ------------------------------------------------------------------

    def _select(self, index: int) -> None:
        self._selected = index
        for row in self._rows:
            row.set_selected(row.index == index)

    def _on_context_menu(self, index: int, global_pos) -> None:
        """Menú contextual: copiar valor / copiar todos."""
        menu = QMenu(self)
        act_copy = menu.addAction(self.tr("Copiar valor"))
        act_copy_all = menu.addAction(self.tr("Copiar todos"))
        action = menu.exec(global_pos)
        clipboard = QApplication.clipboard()
        if action == act_copy:
            clipboard.setText(self.row_value(index))
        elif action == act_copy_all:
            clipboard.setText("\n".join(r.value for r in self._rows))
