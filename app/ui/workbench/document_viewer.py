"""Visor principal de documentos (UI-02, UI-03, UI-04).

QGraphicsView con zoom (rueda), arrastre, overlays semitransparentes
de barcodes/campos IA, y borde coloreado por estado de página.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from app.ui.workbench.page_state import (
    PageState,
    STATE_COLORS,
    ndarray_to_qpixmap,
)

log = logging.getLogger(__name__)

ZOOM_IN_FACTOR = 1.25
ZOOM_OUT_FACTOR = 1.0 / ZOOM_IN_FACTOR
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


class DocumentViewer(QGraphicsView):
    """Visor de documentos con zoom, arrastre y overlays.

    Signals:
        rotation_requested: Emitida al solicitar rotación de 90°.
    """

    rotation_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._overlay_items: list[QGraphicsRectItem] = []
        self._current_zoom: float = 1.0

        # Configurar vista
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        from PySide6.QtGui import QPainter
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate,
        )

    # ------------------------------------------------------------------
    # Imagen y estado
    # ------------------------------------------------------------------

    def set_image(self, image: np.ndarray, state: PageState) -> None:
        """Muestra una imagen y establece el color del borde."""
        self.clear_overlays()

        pixmap = ndarray_to_qpixmap(image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._set_border_color(state)
        self.fit_to_page()

    def set_state(self, state: PageState) -> None:
        """Actualiza solo el color del borde."""
        self._set_border_color(state)

    def clear(self) -> None:
        """Limpia la escena."""
        self.clear_overlays()
        self._scene.clear()
        self._pixmap_item = None

    # ------------------------------------------------------------------
    # Overlays (UI-04)
    # ------------------------------------------------------------------

    def set_overlays(
        self,
        barcodes: list | None = None,
        ai_fields: dict | None = None,
    ) -> None:
        """Dibuja overlays semitransparentes sobre barcodes y campos IA."""
        self.clear_overlays()
        barcodes = barcodes or []

        for bc in barcodes:
            x = getattr(bc, "pos_x", 0)
            y = getattr(bc, "pos_y", 0)
            w = getattr(bc, "pos_w", 0)
            h = getattr(bc, "pos_h", 0)
            if w <= 0 or h <= 0:
                continue

            role = getattr(bc, "role", "")
            if role == "separator":
                color = QColor(251, 140, 0, 80)  # naranja
            else:
                color = QColor(67, 160, 71, 80)  # verde

            rect = self._scene.addRect(
                x, y, w, h,
                QPen(color.darker(120), 2),
                QBrush(color),
            )
            self._overlay_items.append(rect)

    def clear_overlays(self) -> None:
        """Elimina todos los overlays."""
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

    # ------------------------------------------------------------------
    # Zoom y navegación
    # ------------------------------------------------------------------

    def fit_to_page(self) -> None:
        """Ajusta la imagen al tamaño de la vista."""
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self._current_zoom = 1.0
        self.fitInView(
            self._pixmap_item.boundingRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def zoom_in(self) -> None:
        """Acerca la vista."""
        self._apply_zoom(ZOOM_IN_FACTOR)

    def zoom_out(self) -> None:
        """Aleja la vista."""
        self._apply_zoom(ZOOM_OUT_FACTOR)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom con la rueda del ratón."""
        delta = event.angleDelta().y()
        if delta > 0:
            factor = ZOOM_IN_FACTOR
        elif delta < 0:
            factor = ZOOM_OUT_FACTOR
        else:
            return
        self._apply_zoom(factor)

    def _apply_zoom(self, factor: float) -> None:
        """Aplica un factor de zoom con límites."""
        new_zoom = self._current_zoom * factor
        if new_zoom < MIN_ZOOM or new_zoom > MAX_ZOOM:
            return
        self._current_zoom = new_zoom
        self.scale(factor, factor)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _set_border_color(self, state: PageState) -> None:
        """Establece el borde coloreado de la vista (UI-03)."""
        color = STATE_COLORS[state]
        self.setStyleSheet(
            f"QGraphicsView {{ border: 4px solid {color}; }}"
        )
