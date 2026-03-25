"""Tests de deteccion de paginas en blanco."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.image_pipeline import detect_blank


class TestDetectBlank:
    def test_white_image_is_blank(self):
        """Una imagen completamente blanca es blank."""
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        assert detect_blank(img) is True

    def test_black_image_is_not_blank(self):
        """Una imagen completamente negra no es blank."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert detect_blank(img) is False

    def test_image_with_content_is_not_blank(self):
        """Una imagen con contenido significativo no es blank."""
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        # 10% de pixeles negros
        img[:10, :, :] = 0
        assert detect_blank(img, content_threshold=1.0) is False

    def test_almost_blank_below_threshold(self):
        """Imagen con menos del 1% de contenido es blank."""
        img = np.full((1000, 1000, 3), 255, dtype=np.uint8)
        # Solo 5 pixeles negros de 1M total = 0.0005%
        img[0, :5, :] = 0
        assert detect_blank(img, content_threshold=1.0) is True

    def test_custom_threshold(self):
        """Umbral personalizado cambia el resultado."""
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        # 3% de pixeles con contenido
        img[:3, :, :] = 0
        assert detect_blank(img, content_threshold=1.0) is False
        assert detect_blank(img, content_threshold=5.0) is True

    def test_custom_white_tolerance(self):
        """Tolerancia de blanco personalizada.

        gray < white_tolerance → contenido; gray >= tolerance → blanco.
        """
        # Imagen valor 240: con tolerance 245, 240 < 245 → contenido (100%)
        img = np.full((100, 100, 3), 240, dtype=np.uint8)
        assert detect_blank(img, white_tolerance=245) is False
        # Con tolerance 235, 240 >= 235 → blanco (0% contenido)
        assert detect_blank(img, white_tolerance=235) is True
        # Imagen valor 250: con tolerance 245, 250 >= 245 → blanco
        img2 = np.full((100, 100, 3), 250, dtype=np.uint8)
        assert detect_blank(img2, white_tolerance=245) is True

    def test_grayscale_image(self):
        """Funciona con imagenes en escala de grises."""
        img = np.full((100, 100), 255, dtype=np.uint8)
        assert detect_blank(img) is True
        img[:5, :] = 0
        assert detect_blank(img, content_threshold=1.0) is False

    def test_none_image_is_blank(self):
        assert detect_blank(None) is True

    def test_empty_image_is_blank(self):
        img = np.array([], dtype=np.uint8).reshape(0, 0)
        assert detect_blank(img) is True

    def test_scan_like_image_with_margins(self):
        """Simula un escaneo tipico: pagina con contenido en el centro."""
        img = np.full((1000, 800, 3), 250, dtype=np.uint8)
        # Texto simulado: 15% del area con pixeles oscuros
        img[200:350, 100:700, :] = 30
        assert detect_blank(img, content_threshold=1.0) is False

    def test_scan_like_blank_with_noise(self):
        """Pagina en blanco tipica con ruido de escaner."""
        rng = np.random.default_rng(42)
        img = np.full((1000, 800, 3), 252, dtype=np.uint8)
        # Ruido de escaner: algunos pixeles alcanzan 240-250
        noise = rng.integers(240, 255, size=(1000, 800, 3), dtype=np.uint8)
        img = np.minimum(img, noise)
        assert detect_blank(img, content_threshold=1.0, white_tolerance=235) is True
