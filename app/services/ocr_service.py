"""Servicio de OCR unificado.

Soporta RapidOCR (principal), EasyOCR (alternativo) y Tesseract (fallback).
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)


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
    ) -> str:
        """Ejecuta OCR sobre una imagen.

        Args:
            image: Imagen de entrada (BGR o gris).
            engine: "rapidocr", "easyocr" o "tesseract".
            languages: Lista de idiomas (ej: ["es", "en"]).
            full_page: Si False y window está definida, solo esa región.
            window: Región rectangular (x, y, w, h).

        Returns:
            Texto reconocido.
        """
        languages = languages or ["es"]

        # Extraer ROI si se especifica window
        if window and not full_page:
            x, y, w, h = window
            image = image[y:y + h, x:x + w].copy()

        match engine:
            case "rapidocr":
                return self._run_rapidocr(image)
            case "easyocr":
                return self._run_easyocr(image, languages)
            case "tesseract":
                return self._run_tesseract(image, languages)
            case _:
                log.error("Motor OCR desconocido: '%s'", engine)
                return ""

    def _run_rapidocr(self, image: np.ndarray) -> str:
        """OCR con RapidOCR (ONNX Runtime, sin PyTorch)."""
        if self._rapidocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._rapidocr = RapidOCR()
            except ImportError:
                log.error("rapidocr-onnxruntime no instalado")
                return ""

        result, _ = self._rapidocr(image)
        if not result:
            return ""

        # result: list of [bbox, text, confidence]
        lines = [item[1] for item in result]
        return "\n".join(lines)

    def _run_easyocr(self, image: np.ndarray, languages: list[str]) -> str:
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
                return ""

        reader = self._easyocr_readers[lang_key]
        results = reader.readtext(image)
        lines = [text for _, text, _ in results]
        return "\n".join(lines)

    def _run_tesseract(self, image: np.ndarray, languages: list[str]) -> str:
        """OCR con Tesseract."""
        try:
            import pytesseract
        except ImportError:
            log.error("pytesseract no instalado")
            return ""

        lang_str = "+".join(languages)
        gray = image if len(image.shape) == 2 else cv2.cvtColor(
            image, cv2.COLOR_BGR2GRAY,
        )
        return pytesseract.image_to_string(gray, lang=lang_str).strip()
