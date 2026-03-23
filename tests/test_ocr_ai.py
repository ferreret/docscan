"""Tests de OcrService."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.ocr_service import OcrService


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_text_image(text: str = "Hello World 123") -> np.ndarray:
    """Crea una imagen con texto renderizado."""
    img = np.ones((80, 400, 3), dtype=np.uint8) * 255
    cv2.putText(
        img, text, (10, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3,
    )
    return img


# ------------------------------------------------------------------
# OCR Service
# ------------------------------------------------------------------


class TestOcrService:
    def test_rapidocr_basic(self):
        service = OcrService()
        img = _make_text_image("Hello World 123")
        text = service.recognize(img, engine="rapidocr")
        assert len(text) > 0
        # RapidOCR debería reconocer al menos parte del texto
        assert any(w in text for w in ["Hello", "World", "123"])

    def test_rapidocr_empty_image(self):
        service = OcrService()
        blank = np.ones((100, 200, 3), dtype=np.uint8) * 255
        text = service.recognize(blank, engine="rapidocr")
        assert text == ""

    def test_rapidocr_gray_image(self):
        service = OcrService()
        img = _make_text_image()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = service.recognize(gray, engine="rapidocr")
        assert len(text) > 0

    def test_rapidocr_with_window(self):
        service = OcrService()
        img = _make_text_image("Hello World 123")
        # Window que cubre solo parte de la imagen
        text = service.recognize(
            img, engine="rapidocr", full_page=False,
            window=(0, 0, 200, 80),
        )
        assert isinstance(text, str)

    def test_unknown_engine(self):
        service = OcrService()
        blank = np.ones((100, 200, 3), dtype=np.uint8) * 255
        text = service.recognize(blank, engine="unknown_engine")
        assert text == ""
