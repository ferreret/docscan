"""Visor principal de documentos (UI-02, UI-03, UI-04).

QGraphicsView con zoom (rueda), arrastre, overlays semitransparentes
de barcodes/campos IA, y borde coloreado por estado de página.
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QWheelEvent
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

# Paleta de colores vivos para distinguir múltiples barcodes
_BARCODE_PALETTE = [
    ("#e53935", "#ffcdd2"),   # rojo
    ("#1e88e5", "#bbdefb"),   # azul
    ("#43a047", "#c8e6c9"),   # verde
    ("#fb8c00", "#ffe0b2"),   # naranja
    ("#8e24aa", "#e1bee7"),   # púrpura
    ("#00acc1", "#b2ebf2"),   # cian
    ("#d81b60", "#f8bbd0"),   # rosa
    ("#6d4c41", "#d7ccc8"),   # marrón
]


class DocumentViewer(QGraphicsView):
    """Visor de documentos con zoom, arrastre y overlays.

    Signals:
        rotation_requested: Emitida al solicitar rotación de 90°.
        viewer_resized: Emitida al cambiar el tamaño del visor.
    """

    rotation_requested = Signal()
    viewer_resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._overlay_items: list = []
        self._current_zoom: float = 1.0

        # Configurar vista
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.LosslessImageRendering)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate,
        )

    def resizeEvent(self, event) -> None:
        """Notifica que el visor ha cambiado de tamaño."""
        super().resizeEvent(event)
        self.viewer_resized.emit()

    # ------------------------------------------------------------------
    # Imagen y estado
    # ------------------------------------------------------------------

    def set_image(self, image: np.ndarray, state: PageState) -> None:
        """Muestra una imagen y establece el color del borde."""
        self.clear_overlays()

        pixmap = ndarray_to_qpixmap(image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._pixmap_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation,
            )
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
        """Dibuja overlays sobre barcodes con colores distintos por cada uno."""
        self.clear_overlays()
        barcodes = barcodes or []

        # Escalar grosor de borde y fuente proporcionalmente a la imagen
        scene_rect = self._scene.sceneRect()
        img_diag = max(1, (scene_rect.width() ** 2 + scene_rect.height() ** 2) ** 0.5)
        # Para una imagen de ~3000px diagonal, pen_width ~6, font ~24
        pen_width = max(4, int(img_diag / 500))
        margin = pen_width * 2  # Margen extra alrededor del barcode

        for idx, bc in enumerate(barcodes):
            x = getattr(bc, "pos_x", 0)
            y = getattr(bc, "pos_y", 0)
            w = getattr(bc, "pos_w", 0)
            h = getattr(bc, "pos_h", 0)
            if w <= 0 or h <= 0:
                continue

            # Color distinto por barcode (cíclico)
            pen_hex, fill_hex = _BARCODE_PALETTE[idx % len(_BARCODE_PALETTE)]
            pen_color = QColor(pen_hex)
            fill_color = QColor(fill_hex)
            fill_color.setAlpha(100)

            pen = QPen(pen_color, pen_width)
            pen.setStyle(Qt.PenStyle.SolidLine)

            # Rect con margen para que sea más visible
            rx = x - margin
            ry = y - margin
            rw = w + margin * 2
            rh = h + margin * 2

            rect = self._scene.addRect(
                rx, ry, rw, rh,
                pen,
                QBrush(fill_color),
            )
            self._overlay_items.append(rect)

            # Sin etiqueta de texto — el valor se muestra en el panel de barcodes

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

    def zoom_reset(self) -> None:
        """Restaura al tamaño real (100%)."""
        self.resetTransform()
        self._current_zoom = 1.0

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
