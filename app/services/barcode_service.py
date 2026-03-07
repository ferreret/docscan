"""Servicio de lectura de códigos de barras.

Motor 1: pyzbar (rápido, buen soporte 1D)
Motor 2: zxing-cpp (rápido en múltiples códigos, mejor 2D)

Ambos motores devuelven resultados en formato unificado BarcodeResult.
Los resultados se acumulan en page.barcodes sin semántica de rol.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Resultado unificado
# ------------------------------------------------------------------


@dataclass
class BarcodeResult:
    """Resultado de lectura de un código de barras."""

    value: str
    symbology: str
    engine: str  # "motor1" o "motor2"
    step_id: str
    quality: float
    pos_x: int
    pos_y: int
    pos_w: int
    pos_h: int
    role: str = ""  # Asignado por scripts, no por el motor


# ------------------------------------------------------------------
# Motor 1: pyzbar
# ------------------------------------------------------------------

# Mapeo de nombres pyzbar a nombres normalizados
_PYZBAR_SYMBOLOGY_MAP: dict[str, str] = {
    "CODE128": "Code128",
    "CODE39": "Code39",
    "CODE93": "Code93",
    "CODABAR": "Codabar",
    "EAN13": "EAN13",
    "EAN8": "EAN8",
    "UPCA": "UPCA",
    "UPCE": "UPCE",
    "I25": "ITF",
    "QRCODE": "QR",
    "PDF417": "PDF417",
    "DATAMATRIX": "DataMatrix",
}

# Mapeo inverso para filtrar por simbología
_PYZBAR_SYMBOLOGY_REVERSE: dict[str, str] = {
    v: k for k, v in _PYZBAR_SYMBOLOGY_MAP.items()
}


def _read_motor1(
    image: np.ndarray,
    symbologies: list[str],
    step_id: str,
) -> list[BarcodeResult]:
    """Lee barcodes con pyzbar (Motor 1)."""
    try:
        from pyzbar import pyzbar
        from pyzbar.pyzbar import ZBarSymbol
    except ImportError:
        log.warning("pyzbar no disponible (¿falta libzbar?), saltando Motor 1")
        return []

    # Filtrar simbologías si se especificaron
    zbar_symbols = None
    if symbologies:
        zbar_symbols = []
        for sym in symbologies:
            zbar_name = _PYZBAR_SYMBOLOGY_REVERSE.get(sym)
            if zbar_name and hasattr(ZBarSymbol, zbar_name):
                zbar_symbols.append(getattr(ZBarSymbol, zbar_name))

    gray = _ensure_gray(image)
    decoded = pyzbar.decode(gray, symbols=zbar_symbols or None)

    results: list[BarcodeResult] = []
    for d in decoded:
        try:
            value = d.data.decode("utf-8", errors="replace")
        except Exception:
            value = str(d.data)

        sym_name = _PYZBAR_SYMBOLOGY_MAP.get(d.type, d.type)
        rect = d.rect

        results.append(BarcodeResult(
            value=value,
            symbology=sym_name,
            engine="motor1",
            step_id=step_id,
            quality=float(d.quality) if hasattr(d, "quality") else 0.0,
            pos_x=rect.left,
            pos_y=rect.top,
            pos_w=rect.width,
            pos_h=rect.height,
        ))

    return results


# ------------------------------------------------------------------
# Motor 2: zxing-cpp
# ------------------------------------------------------------------

# Mapeo de nombres normalizados a BarcodeFormat de zxingcpp
_ZXING_FORMAT_MAP: dict[str, str] = {
    "Code128": "Code128",
    "Code39": "Code39",
    "Code93": "Code93",
    "Codabar": "Codabar",
    "EAN13": "EAN13",
    "EAN8": "EAN8",
    "UPCA": "UPCA",
    "UPCE": "UPCE",
    "ITF": "ITF",
    "QR": "QRCode",
    "DataMatrix": "DataMatrix",
    "PDF417": "PDF417",
    "Aztec": "Aztec",
    "MaxiCode": "MaxiCode",
    "MicroQRCode": "MicroQRCode",
}

# Mapeo inverso: formato zxingcpp -> nombre normalizado
_ZXING_FORMAT_REVERSE: dict[str, str] = {
    v: k for k, v in _ZXING_FORMAT_MAP.items()
}


def _read_motor2(
    image: np.ndarray,
    symbologies: list[str],
    step_id: str,
) -> list[BarcodeResult]:
    """Lee barcodes con zxing-cpp (Motor 2)."""
    try:
        import zxingcpp
    except ImportError:
        log.warning("zxing-cpp no disponible, saltando Motor 2")
        return []

    # Construir formatos
    formats = None
    if symbologies:
        fmt_names = []
        for sym in symbologies:
            zx_name = _ZXING_FORMAT_MAP.get(sym)
            if zx_name and hasattr(zxingcpp.BarcodeFormat, zx_name):
                fmt_names.append(zx_name)
        if fmt_names:
            formats = zxingcpp.barcode_formats_from_str("|".join(fmt_names))

    gray = _ensure_gray(image)

    kwargs: dict[str, Any] = {}
    if formats is not None:
        kwargs["formats"] = formats

    decoded = zxingcpp.read_barcodes(gray, **kwargs)

    results: list[BarcodeResult] = []
    for d in decoded:
        # Extraer posición del bounding box
        pos = d.position
        points = [
            (pos.top_left.x, pos.top_left.y),
            (pos.top_right.x, pos.top_right.y),
            (pos.bottom_right.x, pos.bottom_right.y),
            (pos.bottom_left.x, pos.bottom_left.y),
        ]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        fmt_name = d.format.name if hasattr(d.format, "name") else str(d.format)
        sym_name = _ZXING_FORMAT_REVERSE.get(fmt_name, fmt_name)

        results.append(BarcodeResult(
            value=d.text,
            symbology=sym_name,
            engine="motor2",
            step_id=step_id,
            quality=0.0,
            pos_x=x_min,
            pos_y=y_min,
            pos_w=x_max - x_min,
            pos_h=y_max - y_min,
        ))

    return results


# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------


def _ensure_gray(image: np.ndarray) -> np.ndarray:
    """Convierte a gris si es necesario."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _apply_window(
    image: np.ndarray,
    window: tuple[int, int, int, int] | None,
) -> tuple[np.ndarray, int, int]:
    """Extrae la región de interés. Devuelve (roi, offset_x, offset_y)."""
    if window is None:
        return image, 0, 0
    x, y, w, h = window
    return image[y:y + h, x:x + w].copy(), x, y


def _rotate_image(image: np.ndarray, angle: int) -> np.ndarray:
    """Rota la imagen 90, 180 o 270 grados."""
    code_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    code = code_map.get(angle)
    if code is not None:
        return cv2.rotate(image, code)
    return image


# ------------------------------------------------------------------
# Servicio principal
# ------------------------------------------------------------------


class BarcodeService:
    """Servicio de lectura de códigos de barras.

    Soporta Motor 1 (pyzbar) y Motor 2 (zxing-cpp).
    Los resultados se acumulan sin semántica de rol.
    """

    def read(
        self,
        image: np.ndarray,
        engine: str = "motor1",
        symbologies: list[str] | None = None,
        regex: str = "",
        regex_include_symbology: bool = False,
        orientations: list[str] | None = None,
        quality_threshold: float = 0.0,
        window: tuple[int, int, int, int] | None = None,
        step_id: str = "",
    ) -> list[BarcodeResult]:
        """Lee códigos de barras de una imagen.

        Args:
            image: Imagen de entrada (BGR o gris).
            engine: "motor1" (pyzbar) o "motor2" (zxing-cpp).
            symbologies: Lista de simbologías a buscar (vacía = todas).
            regex: Expresión regular para filtrar valores.
            regex_include_symbology: Si True, antepone 2 dígitos de
                simbología al valor antes de aplicar el regex.
            orientations: Orientaciones de búsqueda
                ("horizontal", "vertical", "diagonal").
            quality_threshold: Umbral mínimo de calidad.
            window: Región rectangular (x, y, w, h).
            step_id: ID del paso del pipeline.

        Returns:
            Lista de BarcodeResult.
        """
        symbologies = symbologies or []
        orientations = orientations or ["horizontal", "vertical"]

        # Extraer región de interés
        roi, offset_x, offset_y = _apply_window(image, window)

        # Leer en la orientación original
        all_results = self._read_with_engine(
            roi, engine, symbologies, step_id,
        )

        # Leer en orientaciones adicionales
        if "vertical" in orientations:
            rotated = _rotate_image(roi, 90)
            extra = self._read_with_engine(
                rotated, engine, symbologies, step_id,
            )
            # Nota: las posiciones rotadas no son exactas, pero
            # el valor del barcode sí es válido
            all_results.extend(extra)

        if "diagonal" in orientations:
            for angle in (45, 135):
                h, w = roi.shape[:2]
                center = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(roi, matrix, (w, h))
                extra = self._read_with_engine(
                    rotated, engine, symbologies, step_id,
                )
                all_results.extend(extra)

        # Deduplicar por valor
        seen: set[str] = set()
        unique: list[BarcodeResult] = []
        for r in all_results:
            if r.value not in seen:
                seen.add(r.value)
                # Ajustar posiciones al offset de la ventana
                r.pos_x += offset_x
                r.pos_y += offset_y
                unique.append(r)

        # Filtrar por calidad
        if quality_threshold > 0:
            unique = [r for r in unique if r.quality >= quality_threshold]

        # Filtrar por regex
        if regex:
            unique = self._filter_regex(
                unique, regex, regex_include_symbology,
            )

        return unique

    def _read_with_engine(
        self,
        image: np.ndarray,
        engine: str,
        symbologies: list[str],
        step_id: str,
    ) -> list[BarcodeResult]:
        """Despacha la lectura al motor correcto."""
        if engine == "motor1":
            return _read_motor1(image, symbologies, step_id)
        elif engine == "motor2":
            return _read_motor2(image, symbologies, step_id)
        else:
            log.error("Motor de barcode desconocido: '%s'", engine)
            return []

    def _filter_regex(
        self,
        results: list[BarcodeResult],
        regex: str,
        include_symbology: bool,
    ) -> list[BarcodeResult]:
        """Filtra resultados por expresión regular."""
        try:
            pattern = re.compile(regex)
        except re.error as e:
            log.error("Regex inválido '%s': %s", regex, e)
            return results

        filtered: list[BarcodeResult] = []
        for r in results:
            test_value = r.value
            if include_symbology:
                # Prefijo de 2 caracteres con el tipo de simbología
                test_value = f"{r.symbology[:2]}{r.value}"
            if pattern.search(test_value):
                filtered.append(r)

        return filtered
