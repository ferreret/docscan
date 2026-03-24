"""Servicio de OCR unificado.

Soporta RapidOCR (principal), EasyOCR (alternativo) y Tesseract (fallback).
Devuelve resultados estructurados con texto, confianza y coordenadas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class OcrRegion:
    """Región de texto detectada por OCR."""

    text: str
    confidence: float
    x: int
    y: int
    w: int
    h: int


@dataclass
class OcrResult:
    """Resultado completo de un paso OCR."""

    text: str = ""
    regions: list[OcrRegion] = field(default_factory=list)


def _bbox_corners_to_xywh(
    corners: list[list[int | float]],
) -> tuple[int, int, int, int]:
    """Convierte 4 esquinas [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] a (x, y, w, h)."""
    xs = [int(p[0]) for p in corners]
    ys = [int(p[1]) for p in corners]
    x = min(xs)
    y = min(ys)
    return x, y, max(xs) - x, max(ys) - y


def _split_line_into_words(
    line_text: str,
    confidence: float,
    x: int, y: int, w: int, h: int,
) -> list[OcrRegion]:
    """Divide una línea OCR en palabras con bboxes proporcionales."""
    words = line_text.split()
    if not words:
        return []
    if len(words) == 1:
        return [OcrRegion(text=words[0], confidence=confidence,
                          x=x, y=y, w=w, h=h)]

    total_chars = sum(len(word) for word in words)
    if total_chars == 0:
        return []

    regions: list[OcrRegion] = []
    cursor_x = x
    right_edge = x + w
    for i, word in enumerate(words):
        if i == len(words) - 1:
            word_w = right_edge - cursor_x
        else:
            word_w = max(1, int(w * len(word) / total_chars))
        regions.append(OcrRegion(
            text=word, confidence=confidence,
            x=cursor_x, y=y, w=max(1, word_w), h=h,
        ))
        cursor_x += word_w

    return regions


def _build_result_from_lines(
    items: list[tuple[list, str, float]],
) -> OcrResult:
    """Construye OcrResult a partir de detecciones por línea (RapidOCR/EasyOCR)."""
    regions: list[OcrRegion] = []
    lines: list[str] = []
    for bbox, text, conf in items:
        x, y, w, h = _bbox_corners_to_xywh(bbox)
        regions.extend(_split_line_into_words(text, conf, x, y, w, h))
        lines.append(text)
    return OcrResult(text="\n".join(lines), regions=regions)


class OcrService:
    """Servicio de reconocimiento óptico de caracteres.

    Inicializa los motores bajo demanda (lazy) para evitar cargar
    modelos innecesarios.
    """

    def __init__(self) -> None:
        self._rapidocr: Any = None
        self._easyocr_readers: dict[str, Any] = {}

    def recognize(
        self,
        image: np.ndarray,
        engine: str = "rapidocr",
        languages: list[str] | None = None,
        full_page: bool = True,
        window: tuple[int, int, int, int] | None = None,
    ) -> OcrResult:
        """Ejecuta OCR sobre una imagen.

        Args:
            image: Imagen de entrada (BGR o gris).
            engine: "rapidocr", "easyocr" o "tesseract".
            languages: Lista de idiomas (ej: ["es", "en"]).
            full_page: Si False y window está definida, solo esa región.
            window: Región rectangular (x, y, w, h).

        Returns:
            OcrResult con texto concatenado y regiones individuales.
        """
        languages = languages or ["es"]

        # Offset para coordenadas cuando se usa ROI
        offset_x, offset_y = 0, 0
        if window and not full_page:
            x, y, w, h = window
            image = image[y:y + h, x:x + w].copy()
            offset_x, offset_y = x, y

        match engine:
            case "rapidocr":
                result = self._run_rapidocr(image)
            case "easyocr":
                result = self._run_easyocr(image, languages)
            case "tesseract":
                result = self._run_tesseract(image, languages)
            case _:
                log.error("Motor OCR desconocido: '%s'", engine)
                return OcrResult()

        # Ajustar coordenadas si se usó ROI
        if offset_x or offset_y:
            for region in result.regions:
                region.x += offset_x
                region.y += offset_y

        return result

    def _run_rapidocr(self, image: np.ndarray) -> OcrResult:
        """OCR con RapidOCR (ONNX Runtime, sin PyTorch)."""
        if self._rapidocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._rapidocr = RapidOCR()
            except ImportError:
                log.error("rapidocr-onnxruntime no instalado")
                return OcrResult()

        result, _ = self._rapidocr(image)
        if not result:
            return OcrResult()

        # result: list of [bbox_4corners, text, confidence_str]
        items = [(item[0], item[1], float(item[2])) for item in result]
        return _build_result_from_lines(items)

    def _run_easyocr(self, image: np.ndarray, languages: list[str]) -> OcrResult:
        """OCR con EasyOCR (requiere PyTorch)."""
        lang_key = ",".join(sorted(languages))
        if lang_key not in self._easyocr_readers:
            try:
                import easyocr
                self._easyocr_readers[lang_key] = easyocr.Reader(
                    languages, gpu=False,
                )
            except ImportError:
                log.error("easyocr no instalado")
                return OcrResult()

        reader = self._easyocr_readers[lang_key]
        results = reader.readtext(image)

        # results: list of (bbox_4corners, text, confidence)
        return _build_result_from_lines(results)

    def _run_tesseract(self, image: np.ndarray, languages: list[str]) -> OcrResult:
        """OCR con Tesseract."""
        try:
            import pytesseract
        except ImportError:
            log.error("pytesseract no instalado")
            return OcrResult()

        lang_str = "+".join(languages)
        gray = image if len(image.shape) == 2 else cv2.cvtColor(
            image, cv2.COLOR_BGR2GRAY,
        )

        # Usar image_to_data para obtener coordenadas por palabra
        data = pytesseract.image_to_data(
            gray, lang=lang_str, output_type=pytesseract.Output.DICT,
        )

        regions: list[OcrRegion] = []
        # Agrupar palabras por línea para reconstruir el texto
        lines: dict[tuple[int, int, int], list[str]] = {}
        for i in range(len(data["text"])):
            word = data["text"][i].strip()
            conf = int(data["conf"][i])
            if not word or conf < 0:
                continue
            regions.append(OcrRegion(
                text=word,
                confidence=conf / 100.0,
                x=data["left"][i],
                y=data["top"][i],
                w=data["width"][i],
                h=data["height"][i],
            ))
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(line_key, []).append(word)

        full_text = "\n".join(" ".join(words) for words in lines.values())
        return OcrResult(text=full_text, regions=regions)
