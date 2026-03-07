"""Implementación de todas las operaciones de imagen (ImageOp).

Cada operación recibe un ndarray BGR y devuelve un ndarray procesado.
El registro IMAGE_OPS mapea nombre de operación a función.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Tipo de una operación de imagen: (imagen, params) -> imagen
ImageOpFn = Callable[[np.ndarray, dict[str, Any]], np.ndarray]


# ------------------------------------------------------------------
# Operaciones individuales
# ------------------------------------------------------------------


def auto_deskew(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Corrige la inclinación de la imagen automáticamente."""
    gray = _to_gray(image)
    # Binarizar para detectar ángulo
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 10:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect devuelve ángulos en [-90, 0)
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    if abs(angle) < 0.1:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    log.debug("AutoDeskew: ángulo corregido %.2f°", angle)
    return rotated


def convert_to_1bpp(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Convierte a binario (1-bit) con umbral configurable."""
    threshold = params.get("threshold", 128)
    gray = _to_gray(image)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return binary


def crop(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Recorta una región rectangular (x, y, w, h)."""
    x = params.get("x", 0)
    y = params.get("y", 0)
    w = params.get("w", image.shape[1])
    h = params.get("h", image.shape[0])
    return image[y:y + h, x:x + w].copy()


def crop_white_borders(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina bordes blancos alrededor del contenido."""
    margin = params.get("margin", 5)
    gray = _to_gray(image)
    _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return image
    x, y, w, h = cv2.boundingRect(coords)
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(image.shape[1] - x, w + 2 * margin)
    h = min(image.shape[0] - y, h + 2 * margin)
    return image[y:y + h, x:x + w].copy()


def crop_black_borders(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina bordes negros alrededor del contenido."""
    margin = params.get("margin", 5)
    gray = _to_gray(image)
    _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return image
    x, y, w, h = cv2.boundingRect(coords)
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(image.shape[1] - x, w + 2 * margin)
    h = min(image.shape[0] - y, h + 2 * margin)
    return image[y:y + h, x:x + w].copy()


def resize(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Redimensiona por factor o a tamaño absoluto."""
    width = params.get("width")
    height = params.get("height")
    scale = params.get("scale")

    if scale:
        return cv2.resize(image, None, fx=scale, fy=scale)
    if width and height:
        return cv2.resize(image, (width, height))
    return image


def rotate(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Rota 90, 180 o 270 grados."""
    degrees = params.get("degrees", 90)
    code_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    code = code_map.get(degrees)
    if code is None:
        return rotate_angle(image, params)
    return cv2.rotate(image, code)


def rotate_angle(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Rota un ángulo arbitrario."""
    angle = params.get("angle", params.get("degrees", 0))
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)


def set_brightness(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Ajusta brillo (valor entre -100 y 100)."""
    value = params.get("value", 0)
    return cv2.convertScaleAbs(image, alpha=1.0, beta=value)


def set_contrast(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Ajusta contraste (factor, ej: 1.5)."""
    factor = params.get("factor", 1.0)
    return cv2.convertScaleAbs(image, alpha=factor, beta=0)


def remove_lines(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina líneas horizontales, verticales o ambas."""
    direction = params.get("direction", "HV")  # "H", "V", "HV"
    gray = _to_gray(image)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    result = binary.copy()

    if "H" in direction:
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
        result = cv2.subtract(result, h_lines)

    if "V" in direction:
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
        result = cv2.subtract(result, v_lines)

    result = cv2.bitwise_not(result)
    if len(image.shape) == 3:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    return result


def fx_despeckle(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina ruido (despeckle) con filtro de mediana."""
    ksize = params.get("kernel_size", 3)
    if ksize % 2 == 0:
        ksize += 1
    return cv2.medianBlur(image, ksize)


def fx_grayscale(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Convierte a escala de grises."""
    return _to_gray(image)


def fx_negative(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Invierte la imagen (negativo)."""
    return cv2.bitwise_not(image)


def fx_dilate(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Dilatación morfológica."""
    ksize = params.get("kernel_size", 3)
    iterations = params.get("iterations", 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
    return cv2.dilate(image, kernel, iterations=iterations)


def fx_erode(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Erosión morfológica."""
    ksize = params.get("kernel_size", 3)
    iterations = params.get("iterations", 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
    return cv2.erode(image, kernel, iterations=iterations)


def fx_equalize_intensity(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Ecualización de histograma."""
    if len(image.shape) == 2:
        return cv2.equalizeHist(image)
    # Para color, ecualizar canal V en HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv[:, :, 2] = cv2.equalizeHist(hsv[:, :, 2])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def flood_fill(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Relleno por inundación desde un punto."""
    x = params.get("x", 0)
    y = params.get("y", 0)
    color = params.get("color", (255, 255, 255))
    if isinstance(color, list):
        color = tuple(color)
    result = image.copy()
    h, w = result.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(result, mask, (x, y), color)
    return result


def remove_hole_punch(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina marcas de perforadora detectando círculos."""
    gray = _to_gray(image)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
        param1=100, param2=30,
        minRadius=params.get("min_radius", 10),
        maxRadius=params.get("max_radius", 30),
    )
    result = image.copy()
    if circles is not None:
        for circle in np.uint16(np.around(circles[0])):
            cx, cy, r = circle
            fill = (255, 255, 255) if len(image.shape) == 3 else 255
            cv2.circle(result, (cx, cy), r + 2, fill, -1)
    return result


def set_resolution(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Cambia la resolución (DPI). Solo modifica metadatos; no redimensiona."""
    # OpenCV no maneja DPI directamente; esta op es un placeholder
    # que se resuelve al guardar (pymupdf/Pillow escriben DPI)
    return image


def swap_color(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Intercambia un color por otro."""
    src_color = np.array(params.get("from", [0, 0, 0]), dtype=np.uint8)
    dst_color = np.array(params.get("to", [255, 255, 255]), dtype=np.uint8)
    tolerance = params.get("tolerance", 10)

    if len(image.shape) == 2:
        mask = np.abs(image.astype(int) - int(src_color[0])) <= tolerance
        result = image.copy()
        result[mask] = dst_color[0]
        return result

    diff = np.abs(image.astype(int) - src_color.astype(int))
    mask = np.all(diff <= tolerance, axis=2)
    result = image.copy()
    result[mask] = dst_color
    return result


def keep_channel(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Extrae un canal individual (R, G o B)."""
    if len(image.shape) != 3:
        return image
    channel_map = {"B": 0, "G": 1, "R": 2}
    ch = channel_map.get(params.get("channel", "R"), 2)
    return image[:, :, ch]


def remove_channel(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Elimina un canal (pone a 0)."""
    if len(image.shape) != 3:
        return image
    channel_map = {"B": 0, "G": 1, "R": 2}
    ch = channel_map.get(params.get("channel", "R"), 2)
    result = image.copy()
    result[:, :, ch] = 0
    return result


def scale_channel(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Escala un canal por un factor."""
    if len(image.shape) != 3:
        return image
    channel_map = {"B": 0, "G": 1, "R": 2}
    ch = channel_map.get(params.get("channel", "R"), 2)
    factor = params.get("factor", 1.0)
    result = image.copy()
    result[:, :, ch] = np.clip(result[:, :, ch] * factor, 0, 255).astype(np.uint8)
    return result


# ------------------------------------------------------------------
# Utilidades internas
# ------------------------------------------------------------------


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Convierte a gris si la imagen es a color."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


# ------------------------------------------------------------------
# Registro de operaciones
# ------------------------------------------------------------------

IMAGE_OPS: dict[str, ImageOpFn] = {
    "AutoDeskew": auto_deskew,
    "ConvertTo1Bpp": convert_to_1bpp,
    "Crop": crop,
    "CropWhiteBorders": crop_white_borders,
    "CropBlackBorders": crop_black_borders,
    "Resize": resize,
    "Rotate": rotate,
    "RotateAngle": rotate_angle,
    "SetBrightness": set_brightness,
    "SetContrast": set_contrast,
    "RemoveLines": remove_lines,
    "FxDespeckle": fx_despeckle,
    "FxGrayscale": fx_grayscale,
    "FxNegative": fx_negative,
    "FxDilate": fx_dilate,
    "FxErode": fx_erode,
    "FxEqualizeIntensity": fx_equalize_intensity,
    "FloodFill": flood_fill,
    "RemoveHolePunch": remove_hole_punch,
    "SetResolution": set_resolution,
    "SwapColor": swap_color,
    "KeepChannel": keep_channel,
    "RemoveChannel": remove_channel,
    "ScaleChannel": scale_channel,
}


class ImagePipelineService:
    """Servicio para ejecutar operaciones de imagen.

    Args:
        ops: Registro de operaciones. Por defecto IMAGE_OPS.
    """

    def __init__(self, ops: dict[str, ImageOpFn] | None = None) -> None:
        self._ops = ops or IMAGE_OPS

    def execute(
        self,
        image: np.ndarray,
        op_name: str,
        params: dict[str, Any] | None = None,
        window: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """Ejecuta una operación de imagen.

        Args:
            image: Imagen de entrada (ndarray BGR o gris).
            op_name: Nombre de la operación (clave de IMAGE_OPS).
            params: Parámetros de la operación.
            window: Región rectangular (x, y, w, h). Si se indica,
                    la operación se aplica solo a esa región.

        Returns:
            Imagen procesada.

        Raises:
            KeyError: Si la operación no existe.
        """
        fn = self._ops.get(op_name)
        if fn is None:
            raise KeyError(f"Operación de imagen desconocida: '{op_name}'")

        params = params or {}

        if window:
            return self._apply_windowed(image, fn, params, window)

        return fn(image, params)

    def _apply_windowed(
        self,
        image: np.ndarray,
        fn: ImageOpFn,
        params: dict[str, Any],
        window: tuple[int, int, int, int],
    ) -> np.ndarray:
        """Aplica la operación solo a una región rectangular."""
        x, y, w, h = window
        roi = image[y:y + h, x:x + w].copy()
        processed_roi = fn(roi, params)

        result = image.copy()
        # Si la op cambió de color a gris o viceversa, adaptar
        if len(processed_roi.shape) != len(result[y:y + h, x:x + w].shape):
            if len(processed_roi.shape) == 2:
                processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_GRAY2BGR)
            else:
                processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)

        rh, rw = processed_roi.shape[:2]
        result[y:y + rh, x:x + rw] = processed_roi
        return result

    def list_operations(self) -> list[str]:
        """Lista los nombres de todas las operaciones disponibles."""
        return sorted(self._ops.keys())
