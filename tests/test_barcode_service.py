"""Tests del servicio de lectura de barcodes.

Usa imágenes sintéticas con barcodes generados por zxingcpp.
Motor 1 (pyzbar) puede no estar disponible si falta libzbar.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.barcode_service import BarcodeResult, BarcodeService

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_HAS_ZXINGCPP = False
try:
    import zxingcpp
    _HAS_ZXINGCPP = True
except ImportError:
    pass

_HAS_PYZBAR = False
try:
    from pyzbar import pyzbar as _pyzbar_mod
    _HAS_PYZBAR = True
except ImportError:
    pass


def _generate_barcode_image(
    text: str,
    fmt: str = "Code128",
) -> np.ndarray:
    """Genera una imagen con un barcode usando zxingcpp."""
    if not _HAS_ZXINGCPP:
        pytest.skip("zxing-cpp no disponible")

    barcode_format = getattr(zxingcpp.BarcodeFormat, fmt)
    bc = zxingcpp.create_barcode(text, barcode_format)
    img = bc.to_image()
    return np.array(img)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def service():
    return BarcodeService()


@pytest.fixture
def code128_image():
    """Imagen con un Code128 que dice '12345678'."""
    return _generate_barcode_image("12345678", "Code128")


@pytest.fixture
def qr_image():
    """Imagen con un QR Code."""
    return _generate_barcode_image("HELLO-QR-2024", "QRCode")


# ------------------------------------------------------------------
# Tests Motor 2 (zxing-cpp)
# ------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_ZXINGCPP, reason="zxing-cpp no disponible")
class TestMotor2:
    def test_read_code128(self, service, code128_image):
        results = service.read(
            code128_image, engine="motor2", step_id="s1",
        )
        assert len(results) >= 1
        assert results[0].value == "12345678"
        assert results[0].engine == "motor2"
        assert results[0].step_id == "s1"
        assert isinstance(results[0], BarcodeResult)

    def test_read_qr(self, service, qr_image):
        results = service.read(
            qr_image, engine="motor2", step_id="s2",
        )
        assert len(results) >= 1
        assert results[0].value == "HELLO-QR-2024"

    def test_filter_by_symbology(self, service, code128_image):
        # Buscar solo QR — no debe encontrar nada en imagen Code128
        results = service.read(
            code128_image, engine="motor2",
            symbologies=["QR"], step_id="s1",
        )
        assert len(results) == 0

    def test_filter_by_regex(self, service, code128_image):
        # Solo valores que empiecen con 123
        results = service.read(
            code128_image, engine="motor2",
            regex=r"^123", step_id="s1",
        )
        assert len(results) >= 1

    def test_filter_by_regex_excludes(self, service, code128_image):
        # Regex que no matchea
        results = service.read(
            code128_image, engine="motor2",
            regex=r"^ABC", step_id="s1",
        )
        assert len(results) == 0

    def test_empty_image(self, service):
        blank = np.ones((200, 200), dtype=np.uint8) * 255
        results = service.read(blank, engine="motor2", step_id="s1")
        assert len(results) == 0

    def test_window(self, service, code128_image):
        """Leer en una ventana que contenga el barcode."""
        h, w = code128_image.shape[:2]
        results = service.read(
            code128_image, engine="motor2",
            window=(0, 0, w, h), step_id="s1",
        )
        assert len(results) >= 1

    def test_barcode_result_position(self, service, code128_image):
        results = service.read(
            code128_image, engine="motor2", step_id="s1",
        )
        if results:
            r = results[0]
            assert r.pos_w > 0
            assert r.pos_h > 0


# ------------------------------------------------------------------
# Tests Motor 1 (pyzbar) — solo si libzbar está instalada
# ------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_PYZBAR, reason="pyzbar/libzbar no disponible")
class TestMotor1:
    def test_read_code128(self, service, code128_image):
        results = service.read(
            code128_image, engine="motor1", step_id="s1",
        )
        assert len(results) >= 1
        assert results[0].value == "12345678"
        assert results[0].engine == "motor1"


# ------------------------------------------------------------------
# Tests generales
# ------------------------------------------------------------------


class TestBarcodeServiceGeneral:
    def test_unknown_engine(self, service):
        blank = np.ones((100, 100), dtype=np.uint8) * 255
        results = service.read(blank, engine="motor99", step_id="s1")
        assert results == []

    def test_invalid_regex_tolerant(self, service):
        blank = np.ones((100, 100), dtype=np.uint8) * 255
        # Un regex inválido no debe crashear
        results = service.read(
            blank, engine="motor2", regex="[invalid", step_id="s1",
        )
        assert isinstance(results, list)

    def test_result_dataclass(self):
        r = BarcodeResult(
            value="ABC", symbology="Code128", engine="motor1",
            step_id="s1", quality=95.0,
            pos_x=10, pos_y=20, pos_w=100, pos_h=50,
        )
        assert r.role == ""
        r.role = "separator"
        assert r.role == "separator"
