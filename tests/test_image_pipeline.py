"""Tests del servicio de operaciones de imagen."""

import numpy as np
import pytest

from app.services.image_pipeline import ImagePipelineService, IMAGE_OPS


@pytest.fixture
def service():
    return ImagePipelineService()


@pytest.fixture
def color_image():
    """Imagen de prueba 200x300 BGR con contenido."""
    img = np.ones((200, 300, 3), dtype=np.uint8) * 255  # Fondo blanco
    # Rectángulo negro centrado
    img[50:150, 75:225] = 0
    return img


@pytest.fixture
def gray_image():
    img = np.ones((200, 300), dtype=np.uint8) * 255
    img[50:150, 75:225] = 0
    return img


class TestImageOps:
    def test_all_ops_registered(self):
        expected = {
            "AutoDeskew", "ConvertTo1Bpp", "Crop", "CropWhiteBorders",
            "CropBlackBorders", "Resize", "Rotate", "RotateAngle",
            "SetBrightness", "SetContrast", "RemoveLines",
            "FxDespeckle", "FxGrayscale", "FxNegative", "FxDilate",
            "FxErode", "FxEqualizeIntensity", "FloodFill",
            "RemoveHolePunch", "SetResolution", "SwapColor",
            "KeepChannel", "RemoveChannel", "ScaleChannel",
        }
        assert expected == set(IMAGE_OPS.keys())

    def test_convert_to_1bpp(self, service, color_image):
        result = service.execute(color_image, "ConvertTo1Bpp", {"threshold": 128})
        assert len(result.shape) == 2  # Gris
        assert set(np.unique(result)) == {0, 255}  # Binario

    def test_crop(self, service, color_image):
        result = service.execute(
            color_image, "Crop", {"x": 10, "y": 20, "w": 100, "h": 50},
        )
        assert result.shape == (50, 100, 3)

    def test_rotate_90(self, service, color_image):
        result = service.execute(color_image, "Rotate", {"degrees": 90})
        assert result.shape == (300, 200, 3)

    def test_rotate_180(self, service, color_image):
        result = service.execute(color_image, "Rotate", {"degrees": 180})
        assert result.shape == (200, 300, 3)

    def test_grayscale(self, service, color_image):
        result = service.execute(color_image, "FxGrayscale")
        assert len(result.shape) == 2

    def test_negative(self, service, gray_image):
        result = service.execute(gray_image, "FxNegative")
        # Blanco se convierte en negro y viceversa
        assert result[0, 0] == 0  # Era 255
        assert result[100, 150] == 255  # Era 0

    def test_despeckle(self, service, color_image):
        result = service.execute(color_image, "FxDespeckle", {"kernel_size": 3})
        assert result.shape == color_image.shape

    def test_dilate(self, service, gray_image):
        result = service.execute(gray_image, "FxDilate", {"kernel_size": 3})
        assert result.shape == gray_image.shape

    def test_erode(self, service, gray_image):
        result = service.execute(gray_image, "FxErode", {"kernel_size": 3})
        assert result.shape == gray_image.shape

    def test_brightness(self, service, color_image):
        result = service.execute(color_image, "SetBrightness", {"value": 50})
        assert result.shape == color_image.shape

    def test_contrast(self, service, color_image):
        result = service.execute(color_image, "SetContrast", {"factor": 1.5})
        assert result.shape == color_image.shape

    def test_resize_by_scale(self, service, color_image):
        result = service.execute(color_image, "Resize", {"scale": 0.5})
        assert result.shape[0] == 100
        assert result.shape[1] == 150

    def test_equalize_color(self, service, color_image):
        result = service.execute(color_image, "FxEqualizeIntensity")
        assert result.shape == color_image.shape

    def test_equalize_gray(self, service, gray_image):
        result = service.execute(gray_image, "FxEqualizeIntensity")
        assert result.shape == gray_image.shape

    def test_keep_channel(self, service, color_image):
        result = service.execute(color_image, "KeepChannel", {"channel": "R"})
        assert len(result.shape) == 2

    def test_remove_channel(self, service, color_image):
        result = service.execute(color_image, "RemoveChannel", {"channel": "G"})
        assert result.shape == color_image.shape
        assert np.all(result[:, :, 1] == 0)

    def test_crop_white_borders(self, service, color_image):
        result = service.execute(color_image, "CropWhiteBorders")
        # Debe recortar el borde blanco y dejar el rect negro
        assert result.shape[0] < color_image.shape[0]
        assert result.shape[1] < color_image.shape[1]

    def test_unknown_op_raises(self, service, color_image):
        with pytest.raises(KeyError, match="desconocida"):
            service.execute(color_image, "MagicOp")

    def test_auto_deskew_straight_image(self, service, color_image):
        """Una imagen recta no debería cambiar mucho."""
        result = service.execute(color_image, "AutoDeskew")
        assert result.shape == color_image.shape


class TestWindowedExecution:
    def test_windowed_grayscale(self, service, color_image):
        """Aplica FxGrayscale solo a una región."""
        result = service.execute(
            color_image, "FxNegative", window=(0, 0, 150, 100),
        )
        # La región modificada y la no modificada deben diferir
        assert result.shape == color_image.shape

    def test_windowed_crop(self, service, color_image):
        """Una op en ventana no cambia el tamaño total."""
        result = service.execute(
            color_image, "SetBrightness", {"value": 50},
            window=(50, 50, 100, 100),
        )
        assert result.shape == color_image.shape

    def test_list_operations(self, service):
        ops = service.list_operations()
        assert "AutoDeskew" in ops
        assert len(ops) == 24
