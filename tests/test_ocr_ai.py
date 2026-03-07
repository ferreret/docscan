"""Tests de OcrService y AiService."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import pytest

from app.services.ocr_service import OcrService
from app.services.ai_service import AiService
from app.providers.base_provider import BaseProvider


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


class MockProvider(BaseProvider):
    """Proveedor mock para tests sin API externa."""

    def __init__(self, fields: dict[str, str] | None = None) -> None:
        self._fields = fields or {"numero": "12345"}

    def extract_fields(
        self, image: Any, prompt: str, fields: list[dict[str, str]],
    ) -> dict[str, str]:
        return {f["name"]: self._fields.get(f["name"], "") for f in fields}

    def classify_document(
        self, image: Any, classes: list[str],
    ) -> str:
        return classes[0] if classes else ""


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


# ------------------------------------------------------------------
# AI Service
# ------------------------------------------------------------------


class TestAiService:
    def test_extract_with_mock_provider(self):
        provider = MockProvider(fields={"numero": "F-2024-001"})
        service = AiService(providers={"mock": provider})

        template = {
            "prompt": "Extrae los campos",
            "fields": [
                {"name": "numero", "type": "text", "description": "Número"},
            ],
        }
        service._template_loader = lambda tid: template

        img = np.ones((100, 100, 3), dtype=np.uint8)
        result = service.extract(img, provider="mock", template_id=1)
        assert result["numero"] == "F-2024-001"

    def test_classify_with_mock_provider(self):
        provider = MockProvider()
        service = AiService(providers={"mock": provider})

        img = np.ones((100, 100, 3), dtype=np.uint8)
        result = service.classify(
            img, provider="mock",
            classes=["factura", "albarán", "contrato"],
        )
        assert result == "factura"

    def test_local_ocr_provider(self):
        ocr = OcrService()
        service = AiService(ocr_service=ocr)

        img = _make_text_image("Factura 12345")
        result = service.extract(img, provider="local_ocr")
        assert "ocr_text" in result
        assert len(result["ocr_text"]) > 0

    def test_unknown_provider_raises(self):
        service = AiService()
        img = np.ones((100, 100, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="no configurado"):
            service.extract(img, provider="nonexistent", template_id=1)

    def test_missing_template_raises(self):
        provider = MockProvider()
        service = AiService(providers={"mock": provider})
        img = np.ones((100, 100, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="no encontrada"):
            service.extract(img, provider="mock", template_id=999)

    def test_register_provider(self):
        service = AiService()
        provider = MockProvider()
        service.register_provider("test", provider)

        template = {
            "prompt": "Test",
            "fields": [{"name": "x", "type": "text"}],
        }
        service._template_loader = lambda tid: template

        img = np.ones((100, 100, 3), dtype=np.uint8)
        result = service.extract(img, provider="test", template_id=1)
        assert isinstance(result, dict)
