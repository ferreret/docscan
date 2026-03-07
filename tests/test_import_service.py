"""Tests del servicio de importación."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest

from app.services.import_service import ImportService, IMAGE_EXTENSIONS, PDF_EXTENSIONS


@pytest.fixture
def service() -> ImportService:
    return ImportService(default_dpi=150)


@pytest.fixture
def tmp_image(tmp_path: Path) -> Path:
    """Crea una imagen JPEG temporal."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    cv2.putText(img, "Test", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
    path = tmp_path / "test.jpg"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def tmp_png(tmp_path: Path) -> Path:
    img = np.ones((50, 80, 3), dtype=np.uint8) * 128
    path = tmp_path / "test.png"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def tmp_bmp(tmp_path: Path) -> Path:
    img = np.ones((50, 80, 3), dtype=np.uint8) * 200
    path = tmp_path / "test.bmp"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def tmp_tiff_single(tmp_path: Path) -> Path:
    img = np.zeros((60, 100), dtype=np.uint8)
    path = tmp_path / "single.tiff"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def tmp_tiff_multi(tmp_path: Path) -> Path:
    """Crea un TIFF multipágina."""
    path = tmp_path / "multi.tiff"
    imgs = [
        np.zeros((60, 100), dtype=np.uint8),
        np.ones((60, 100), dtype=np.uint8) * 128,
        np.ones((60, 100), dtype=np.uint8) * 255,
    ]
    cv2.imwritemulti(str(path), imgs)
    return path


@pytest.fixture
def tmp_pdf(tmp_path: Path) -> Path:
    """Crea un PDF de 2 páginas con pymupdf."""
    path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=200, height=100)
        page.insert_text((10, 50), f"Pagina {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


# ------------------------------------------------------------------
# Tests de import_file
# ------------------------------------------------------------------


class TestImportFile:
    def test_import_jpeg(self, service: ImportService, tmp_image: Path):
        images = service.import_file(tmp_image)
        assert len(images) == 1
        assert images[0].shape == (100, 200, 3)

    def test_import_png(self, service: ImportService, tmp_png: Path):
        images = service.import_file(tmp_png)
        assert len(images) == 1
        assert images[0].shape[:2] == (50, 80)

    def test_import_bmp(self, service: ImportService, tmp_bmp: Path):
        images = service.import_file(tmp_bmp)
        assert len(images) == 1

    def test_import_tiff_single(self, service: ImportService, tmp_tiff_single: Path):
        images = service.import_file(tmp_tiff_single)
        assert len(images) == 1

    def test_import_tiff_multi(self, service: ImportService, tmp_tiff_multi: Path):
        images = service.import_file(tmp_tiff_multi)
        assert len(images) == 3

    def test_import_pdf(self, service: ImportService, tmp_pdf: Path):
        images = service.import_file(tmp_pdf)
        assert len(images) == 2
        # Cada página debe ser una imagen BGR
        for img in images:
            assert img.ndim == 3
            assert img.shape[2] == 3

    def test_import_pdf_custom_dpi(self, service: ImportService, tmp_pdf: Path):
        imgs_150 = service.import_file(tmp_pdf, dpi=150)
        imgs_300 = service.import_file(tmp_pdf, dpi=300)
        # Mayor DPI → mayor resolución
        assert imgs_300[0].shape[0] > imgs_150[0].shape[0]

    def test_file_not_found(self, service: ImportService):
        with pytest.raises(FileNotFoundError):
            service.import_file("/nonexistent/file.jpg")

    def test_unsupported_format(self, service: ImportService, tmp_path: Path):
        path = tmp_path / "test.xyz"
        path.write_text("not an image")
        with pytest.raises(ValueError, match="no soportado"):
            service.import_file(path)

    def test_accepts_string_path(self, service: ImportService, tmp_image: Path):
        images = service.import_file(str(tmp_image))
        assert len(images) == 1


# ------------------------------------------------------------------
# Tests de import_folder
# ------------------------------------------------------------------


class TestImportFolder:
    def test_import_folder_basic(
        self, service: ImportService, tmp_path: Path,
        tmp_image: Path, tmp_png: Path,
    ):
        images = service.import_folder(tmp_path)
        assert len(images) == 2

    def test_import_folder_with_pdf(
        self, service: ImportService, tmp_path: Path,
        tmp_image: Path, tmp_pdf: Path,
    ):
        images = service.import_folder(tmp_path)
        # 1 JPEG + 2 páginas PDF = 3
        assert len(images) == 3

    def test_import_folder_recursive(self, service: ImportService, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "a.jpg"), img)
        cv2.imwrite(str(sub / "b.jpg"), img)

        flat = service.import_folder(tmp_path, recursive=False)
        assert len(flat) == 1

        recursive = service.import_folder(tmp_path, recursive=True)
        assert len(recursive) == 2

    def test_import_folder_ignores_unsupported(
        self, service: ImportService, tmp_path: Path,
    ):
        (tmp_path / "readme.txt").write_text("not an image")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "a.png"), img)
        images = service.import_folder(tmp_path)
        assert len(images) == 1

    def test_import_folder_empty(self, service: ImportService, tmp_path: Path):
        images = service.import_folder(tmp_path)
        assert images == []

    def test_import_folder_not_a_dir(self, service: ImportService, tmp_image: Path):
        with pytest.raises(NotADirectoryError):
            service.import_folder(tmp_image)

    def test_import_folder_alphabetical_order(
        self, service: ImportService, tmp_path: Path,
    ):
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        for name in ["c.jpg", "a.jpg", "b.jpg"]:
            cv2.imwrite(str(tmp_path / name), img)
        # Debe importar en orden alfabético (a, b, c)
        images = service.import_folder(tmp_path)
        assert len(images) == 3


# ------------------------------------------------------------------
# Tests auxiliares
# ------------------------------------------------------------------


class TestSupportedExtensions:
    def test_get_supported_extensions(self, service: ImportService):
        exts = service.get_supported_extensions()
        assert ".pdf" in exts
        assert ".jpg" in exts
        assert ".tiff" in exts
        assert exts == sorted(exts)

    def test_constants(self):
        assert ".pdf" in PDF_EXTENSIONS
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".tif" in IMAGE_EXTENSIONS
