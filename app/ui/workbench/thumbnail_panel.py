"""Panel de miniaturas de páginas (UI-01).

Muestra las miniaturas scrollables con borde coloreado según el estado
de cada página. Click selecciona, doble-click navega.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.workbench.page_state import (
    PageState,
    state_color,
    ndarray_to_qpixmap,
)

log = logging.getLogger(__name__)

THUMBNAIL_WIDTH = 140
# Grosor total alrededor de la imagen (borde + marco), igual con y sin selección.
_FRAME = 7
_BORDER = 2
_SELECTED_BORDER = 3


class ThumbnailItem(QLabel):
    """Miniatura individual con borde coloreado."""

    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, page_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page_index = page_index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(THUMBNAIL_WIDTH + 8 + 2 * _FRAME)
        self._selected = False
        self._state = PageState.NO_RECOGNITION

    def set_state(self, state: PageState) -> None:
        """Actualiza el color del borde según el estado."""
        self._state = state
        self._apply_style()

    def set_selected(self, selected: bool, state: PageState) -> None:
        """Marca o desmarca la miniatura como seleccionada."""
        self._selected = selected
        self._state = state
        self._apply_style()

    def _apply_style(self) -> None:
        """Pinta el borde de estado y, si está seleccionada, el marco de acento.

        El borde exterior siempre lleva el color del estado (revisión,
        separador…). La seleccionada añade un marco macizo del color de acento
        entre ese borde y la imagen: antes solo se distinguía por 1 px más de
        borde y un fondo al 16 % que quedaba tapado por la página. El grosor
        total es el mismo en los dos casos, así que nada se mueve al cambiar
        de página.
        """
        from app.ui.palette import color

        state = state_color(self._state)
        if self._selected:
            self.setStyleSheet(
                f"QLabel {{ border: {_SELECTED_BORDER}px solid {state}; "
                f"background-color: {color('accent')}; "
                f"padding: {_FRAME - _SELECTED_BORDER}px; }}"
            )
        else:
            self.setStyleSheet(
                f"QLabel {{ border: {_BORDER}px solid {state}; "
                f"background-color: transparent; "
                f"padding: {_FRAME - _BORDER}px; }}"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.page_index)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.page_index)


class ThumbnailPanel(QWidget):
    """Panel lateral de miniaturas scrollable.

    Signals:
        page_selected: Emitida al hacer click en una miniatura.
        page_double_clicked: Emitida al hacer doble click.
    """

    page_selected = Signal(int)
    page_double_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thumbnails: dict[int, ThumbnailItem] = {}
        self._states: dict[int, PageState] = {}
        self._current_index: int = -1
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._container_layout.setSpacing(4)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        self.setFixedWidth(THUMBNAIL_WIDTH + 38 + 2 * _FRAME)

    @staticmethod
    def _make_pixmap(image: np.ndarray) -> QPixmap:
        """Escala una imagen a miniatura y devuelve QPixmap."""
        h, w = image.shape[:2]
        scale = THUMBNAIL_WIDTH / max(w, 1)
        thumb = cv2.resize(
            image,
            (THUMBNAIL_WIDTH, int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )
        return ndarray_to_qpixmap(thumb)

    def add_thumbnail(
        self,
        page_index: int,
        image: np.ndarray,
        state: PageState = PageState.NO_RECOGNITION,
    ) -> None:
        """Añade una miniatura al panel."""
        item = ThumbnailItem(page_index)
        item.setPixmap(self._make_pixmap(image))
        item.set_state(state)
        item.clicked.connect(self._on_item_clicked)
        item.double_clicked.connect(self.page_double_clicked.emit)

        self._thumbnails[page_index] = item
        self._states[page_index] = state
        self._container_layout.addWidget(item)

    def update_thumbnail_image(self, page_index: int, image: np.ndarray) -> None:
        """Reemplaza la imagen de una miniatura existente."""
        item = self._thumbnails.get(page_index)
        if item is None:
            return
        item.setPixmap(self._make_pixmap(image))

    def update_thumbnail_state(self, page_index: int, state: PageState) -> None:
        """Actualiza el color del borde de una miniatura."""
        self._states[page_index] = state
        item = self._thumbnails.get(page_index)
        if item is None:
            return
        is_current = page_index == self._current_index
        item.set_selected(is_current, state)

    def set_current(self, page_index: int) -> None:
        """Selecciona una miniatura y hace scroll hasta ella."""
        # Deseleccionar anterior
        if self._current_index in self._thumbnails:
            old = self._thumbnails[self._current_index]
            old.set_selected(
                False,
                self._states.get(
                    self._current_index,
                    PageState.NO_RECOGNITION,
                ),
            )

        self._current_index = page_index
        item = self._thumbnails.get(page_index)
        if item is None:
            return

        item.set_selected(
            True,
            self._states.get(
                page_index,
                PageState.NO_RECOGNITION,
            ),
        )
        self._scroll.ensureWidgetVisible(item)

    def clear(self) -> None:
        """Elimina todas las miniaturas."""
        for item in self._thumbnails.values():
            self._container_layout.removeWidget(item)
            item.deleteLater()
        self._thumbnails.clear()
        self._states.clear()
        self._current_index = -1

    @property
    def count(self) -> int:
        return len(self._thumbnails)

    def _on_item_clicked(self, page_index: int) -> None:
        self.set_current(page_index)
        self.page_selected.emit(page_index)
