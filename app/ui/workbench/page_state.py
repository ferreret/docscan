"""Estado visual de página y utilidades de conversión de imagen.

Determina el color del borde según la prioridad UI-03:
rojo > naranja > azul > verde > gris.
"""

from __future__ import annotations

from enum import Enum

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap


class PageState(Enum):
    """Estado visual de una página (UI-03)."""

    NEEDS_REVIEW = "needs_review"
    SEPARATOR_BARCODE = "separator"
    AI_FIELDS = "ai_fields"
    BARCODE_NO_ROLE = "barcode_no_role"
    NO_RECOGNITION = "no_recognition"


STATE_COLORS: dict[PageState, str] = {
    PageState.NEEDS_REVIEW: "#e53935",
    PageState.SEPARATOR_BARCODE: "#fb8c00",
    PageState.AI_FIELDS: "#1e88e5",
    PageState.BARCODE_NO_ROLE: "#43a047",
    PageState.NO_RECOGNITION: "#9e9e9e",
}


def determine_page_state(
    needs_review: bool = False,
    barcodes: list | None = None,
    ai_fields_json: str = "{}",
) -> PageState:
    """Determina el estado visual de una página (prioridad UI-03).

    Args:
        needs_review: Si la página necesita revisión.
        barcodes: Lista de objetos barcode (con atributo ``role``).
        ai_fields_json: JSON de campos IA extraídos.
    """
    if needs_review:
        return PageState.NEEDS_REVIEW

    barcodes = barcodes or []
    has_separator = any(
        getattr(b, "role", "") == "separator" for b in barcodes
    )
    if has_separator:
        return PageState.SEPARATOR_BARCODE

    if ai_fields_json not in ("", "{}", "null"):
        return PageState.AI_FIELDS

    if barcodes:
        return PageState.BARCODE_NO_ROLE

    return PageState.NO_RECOGNITION


def ndarray_to_qpixmap(image: np.ndarray) -> QPixmap:
    """Convierte una imagen numpy (BGR u gris) a QPixmap."""
    if image is None:
        return QPixmap()

    if len(image.shape) == 2:
        # Escala de grises
        h, w = image.shape
        qimg = QImage(image.data, w, h, w, QImage.Format.Format_Grayscale8)
    elif image.shape[2] == 4:
        # BGRA -> RGBA
        rgba = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        h, w = rgba.shape[:2]
        qimg = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    else:
        # BGR -> RGB
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)

    return QPixmap.fromImage(qimg.copy())
