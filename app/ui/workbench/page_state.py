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

    EXCLUDED = "excluded"
    NEEDS_REVIEW = "needs_review"
    SEPARATOR_BARCODE = "separator"
    CUSTOM_FIELDS = "custom_fields"
    BARCODE_NO_ROLE = "barcode_no_role"
    NO_RECOGNITION = "no_recognition"


STATE_COLORS: dict[PageState, str] = {
    PageState.EXCLUDED: "#d32f2f",
    PageState.NEEDS_REVIEW: "#e53935",
    PageState.SEPARATOR_BARCODE: "#fb8c00",
    PageState.CUSTOM_FIELDS: "#1e88e5",
    PageState.BARCODE_NO_ROLE: "#43a047",
    PageState.NO_RECOGNITION: "#9e9e9e",
}


def determine_page_state(
    needs_review: bool = False,
    barcodes: list | None = None,
    custom_fields_json: str = "{}",
    is_excluded: bool = False,
) -> PageState:
    """Determina el estado visual de una página (prioridad UI-03).

    Args:
        needs_review: Si la página necesita revisión.
        barcodes: Lista de objetos barcode (con atributo ``role``).
        custom_fields_json: JSON de campos personalizados.
        is_excluded: Si la página está marcada para excluir.
    """
    if is_excluded:
        return PageState.EXCLUDED

    if needs_review:
        return PageState.NEEDS_REVIEW

    barcodes = barcodes or []
    has_separator = any(
        getattr(b, "role", "") == "separator" for b in barcodes
    )
    if has_separator:
        return PageState.SEPARATOR_BARCODE

    if custom_fields_json not in ("", "{}", "null"):
        return PageState.CUSTOM_FIELDS

    if barcodes:
        return PageState.BARCODE_NO_ROLE

    return PageState.NO_RECOGNITION


def _is_binary(image: np.ndarray) -> bool:
    """Detecta si una imagen 2D tiene solo valores 0 y 255 (1-bit efectivo)."""
    if image.ndim != 2:
        return False
    unique = np.unique(image)
    return len(unique) <= 2 and set(unique.tolist()).issubset({0, 255})


def _antialias_binary(image: np.ndarray) -> np.ndarray:
    """Aplica anti-aliasing a una imagen binaria (0/255) sin cambiar dimensiones.

    Un Gaussian blur ligero (kernel 3x3, sigma=0.8) crea valores intermedios
    de gris en los bordes del texto. Esto permite que la interpolación bilineal
    de Qt produzca transiciones suaves al hacer zoom out, igual que los visores
    profesionales. A zoom 1:1 en 300 DPI el efecto es imperceptible.
    """
    if not _is_binary(image):
        return image
    return cv2.GaussianBlur(image, (3, 3), sigmaX=0.8)


def ndarray_to_qpixmap(image: np.ndarray) -> QPixmap:
    """Convierte una imagen numpy (BGR u gris) a QPixmap.

    Las imágenes binarias (1-bit, valores 0/255) se suavizan con un
    Gaussian blur ligero para que la interpolación bilineal de Qt
    produzca bordes anti-aliased al escalar.
    """
    if image is None:
        return QPixmap()

    if image.ndim == 2:
        # Gris o binario — anti-alias si es binario
        display_image = _antialias_binary(image)
        h, w = display_image.shape
        qimg = QImage(
            display_image.data, w, h, w, QImage.Format.Format_Grayscale8,
        )
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
