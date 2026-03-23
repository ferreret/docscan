"""Tests para ImageLib — librería de tratamiento de imágenes."""

import numpy as np
import pytest
from pathlib import Path

from app.services.image_lib import ImageLib


@pytest.fixture
def color_image():
    """Imagen BGR de prueba 100x80 con color."""
    img = np.zeros((80, 100, 3), dtype=np.uint8)
    img[:, :50] = [255, 0, 0]   # Azul (BGR)
    img[:, 50:] = [0, 255, 0]   # Verde (BGR)
    return img


@pytest.fixture
def gray_image():
    """Imagen gris de prueba 80x100."""
    return np.full((80, 100), 128, dtype=np.uint8)


@pytest.fixture
def output_dir(tmp_path):
    """Directorio temporal de salida."""
    d = tmp_path / "output"
    d.mkdir()
    return d


# ------------------------------------------------------------------
# Guardar / Cargar
# ------------------------------------------------------------------

class TestSaveLoad:
    def test_save_jpeg_quality(self, color_image, output_dir):
        """JPEG con calidad baja debe pesar menos que calidad alta."""
        low = output_dir / "low.jpg"
        high = output_dir / "high.jpg"
        ImageLib.save(color_image, low, quality=10)
        ImageLib.save(color_image, high, quality=95)
        assert low.stat().st_size < high.stat().st_size

    def test_save_tiff_compression(self, color_image, output_dir):
        """TIFF con LZW debe pesar menos que sin comprimir."""
        none_path = output_dir / "none.tiff"
        lzw_path = output_dir / "lzw.tiff"
        ImageLib.save(color_image, none_path, compression="none")
        ImageLib.save(color_image, lzw_path, compression="lzw")
        assert lzw_path.stat().st_size < none_path.stat().st_size

    def test_save_png_compression(self, color_image, output_dir):
        """PNG con compresión 9 debe pesar <= compresión 0."""
        low = output_dir / "low.png"
        high = output_dir / "high.png"
        ImageLib.save(color_image, low, png_level=0)
        ImageLib.save(color_image, high, png_level=9)
        assert high.stat().st_size <= low.stat().st_size

    def test_save_with_dpi(self, color_image, output_dir):
        """Guardar con DPI y verificar que se puede leer."""
        path = output_dir / "dpi.tiff"
        ImageLib.save(color_image, path, dpi=300)
        dpi = ImageLib.get_dpi(path)
        assert dpi[0] == pytest.approx(300.0, abs=1.0)

    def test_load_formats(self, color_image, output_dir):
        """Cargar imágenes guardadas en varios formatos."""
        for ext in (".jpg", ".png", ".tiff", ".bmp"):
            path = output_dir / f"test{ext}"
            ImageLib.save(color_image, path)
            imgs = ImageLib.load(path)
            assert len(imgs) == 1
            assert imgs[0].shape[:2] == (80, 100)

    def test_load_not_found(self):
        """Cargar fichero inexistente lanza FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ImageLib.load("/tmp/no_existe_xyz.png")

    def test_save_grayscale(self, gray_image, output_dir):
        """Guardar y cargar imagen gris."""
        path = output_dir / "gray.png"
        ImageLib.save(gray_image, path)
        imgs = ImageLib.load(path)
        assert len(imgs) == 1
        assert len(imgs[0].shape) == 2  # Gris = 2D


# ------------------------------------------------------------------
# Conversión
# ------------------------------------------------------------------

class TestConvert:
    def test_convert_roundtrip(self, color_image, output_dir):
        """Convertir de PNG a JPEG y verificar dimensiones."""
        # Guardar como PNG primero
        png_path = output_dir / "src.png"
        ImageLib.save(color_image, png_path)

        # Convertir a JPEG
        jpg_path = ImageLib.convert(color_image, "jpg", output_dir / "out")
        assert jpg_path.suffix == ".jpg"
        assert jpg_path.exists()

        imgs = ImageLib.load(jpg_path)
        assert imgs[0].shape[:2] == (80, 100)


# ------------------------------------------------------------------
# Merge / Split
# ------------------------------------------------------------------

class TestMergeSplit:
    def test_merge_to_pdf(self, color_image, output_dir):
        """Merge de imágenes a PDF."""
        pdf_path = output_dir / "merged.pdf"
        result = ImageLib.merge_to_pdf(
            [color_image, color_image], pdf_path, dpi=150,
        )
        assert result == pdf_path
        assert pdf_path.exists()

        # Verificar que se puede abrir como PDF
        pages = ImageLib.load(pdf_path)
        assert len(pages) == 2

    def test_merge_to_tiff(self, color_image, output_dir):
        """Merge de imágenes a TIFF multipágina."""
        tiff_path = output_dir / "merged.tiff"
        result = ImageLib.merge_to_tiff(
            [color_image, color_image, color_image], tiff_path,
        )
        assert result == tiff_path
        assert tiff_path.exists()

        pages = ImageLib.load(tiff_path)
        assert len(pages) == 3

    def test_split_pdf(self, color_image, output_dir):
        """Split de un PDF en imágenes individuales."""
        pdf_path = output_dir / "to_split.pdf"
        ImageLib.merge_to_pdf([color_image, color_image], pdf_path)

        split_dir = output_dir / "split_out"
        pages = ImageLib.split(pdf_path, split_dir, format="png")
        assert len(pages) == 2
        for p in pages:
            assert p.exists()
            assert p.suffix == ".png"

    def test_split_tiff(self, color_image, output_dir):
        """Split de un TIFF multipágina."""
        tiff_path = output_dir / "multi.tiff"
        ImageLib.merge_to_tiff([color_image, color_image], tiff_path)

        split_dir = output_dir / "split_tiff"
        pages = ImageLib.split(tiff_path, split_dir, format="jpg")
        assert len(pages) == 2


# ------------------------------------------------------------------
# DPI
# ------------------------------------------------------------------

class TestDpi:
    def test_get_dpi_default(self, color_image, output_dir):
        """Sin DPI explícito, devuelve algo razonable."""
        path = output_dir / "no_dpi.png"
        ImageLib.save(color_image, path)
        dpi = ImageLib.get_dpi(path)
        assert isinstance(dpi, tuple)
        assert len(dpi) == 2

    def test_resize_to_dpi(self, color_image):
        """Resize a DPI diferente cambia dimensiones."""
        # De 300 a 150 → mitad de tamaño
        resized = ImageLib.resize_to_dpi(color_image, 300, 150)
        assert resized.shape[0] == 40  # 80/2
        assert resized.shape[1] == 50  # 100/2

    def test_resize_same_dpi(self, color_image):
        """Resize al mismo DPI no cambia nada."""
        result = ImageLib.resize_to_dpi(color_image, 300, 300)
        assert result.shape == color_image.shape


# ------------------------------------------------------------------
# Modo de color
# ------------------------------------------------------------------

class TestColorMode:
    def test_to_grayscale(self, color_image):
        """Convertir a escala de grises."""
        gray = ImageLib.to_grayscale(color_image)
        assert len(gray.shape) == 2

    def test_to_grayscale_idempotent(self, gray_image):
        """Convertir gris a gris no cambia nada."""
        result = ImageLib.to_grayscale(gray_image)
        assert np.array_equal(result, gray_image)

    def test_to_bw(self, color_image):
        """Convertir a blanco y negro."""
        bw = ImageLib.to_bw(color_image, threshold=128)
        assert len(bw.shape) == 2
        unique = set(np.unique(bw))
        assert unique.issubset({0, 255})

    def test_to_color(self, gray_image):
        """Convertir gris a color."""
        color = ImageLib.to_color(gray_image)
        assert color.shape == (80, 100, 3)

    def test_to_color_idempotent(self, color_image):
        """Convertir color a color no cambia nada."""
        result = ImageLib.to_color(color_image)
        assert np.array_equal(result, color_image)

    def test_get_color_mode_color(self, color_image):
        assert ImageLib.get_color_mode(color_image) == "color"

    def test_get_color_mode_gray(self, gray_image):
        assert ImageLib.get_color_mode(gray_image) == "grayscale"

    def test_get_color_mode_bw(self):
        bw = np.zeros((50, 50), dtype=np.uint8)
        bw[:25] = 255
        assert ImageLib.get_color_mode(bw) == "bw"
