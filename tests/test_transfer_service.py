"""Tests del servicio de transferencia."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest

from app.services.transfer_service import (
    TransferConfig,
    TransferResult,
    TransferService,
    parse_transfer_config,
)


@pytest.fixture
def service() -> TransferService:
    return TransferService()


@pytest.fixture
def sample_pages(tmp_path: Path) -> list[dict]:
    """Crea páginas de prueba con imágenes en disco."""
    pages = []
    for i in range(3):
        img = np.ones((100, 200, 3), dtype=np.uint8) * (i * 80)
        cv2.putText(
            img, f"Page {i}", (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2,
        )
        path = tmp_path / "source" / f"page_{i:04d}.tiff"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), img)
        pages.append({
            "image_path": str(path),
            "page_index": i,
            "ocr_text": f"Texto OCR página {i}",
            "fields": {"numero": f"F-{i:03d}", "ref": f"REF-{i}", "tipo": "factura"},
        })
    return pages


# ------------------------------------------------------------------
# TransferConfig
# ------------------------------------------------------------------


class TestTransferConfig:
    def test_defaults(self):
        config = TransferConfig()
        assert config.mode == "folder"
        assert config.pdf_dpi == 200

    def test_parse_from_json(self):
        data = json.dumps({
            "mode": "pdf",
            "destination": "/tmp/output",
            "pdf_dpi": 300,
        })
        config = parse_transfer_config(data)
        assert config.mode == "pdf"
        assert config.destination == "/tmp/output"
        assert config.pdf_dpi == 300

    def test_parse_empty_json(self):
        config = parse_transfer_config("{}")
        assert config.mode == "folder"

    def test_parse_ignores_unknown_fields(self):
        data = json.dumps({"mode": "csv", "unknown_field": 42})
        config = parse_transfer_config(data)
        assert config.mode == "csv"


# ------------------------------------------------------------------
# Transferencia a carpeta
# ------------------------------------------------------------------


class TestFolderTransfer:
    def test_basic_copy(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        assert result.success
        assert result.files_transferred == 3
        output_dir = Path(result.output_path)
        assert output_dir.exists()
        assert len(list(output_dir.glob("*.*"))) == 3

    def test_creates_subdirs(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
            create_subdirs=True,
        )
        result = service.transfer(sample_pages, config, batch_id=42)
        assert "batch_42" in result.output_path

    def test_no_subdirs(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
            create_subdirs=False,
        )
        result = service.transfer(sample_pages, config, batch_id=42)
        assert "batch_42" not in result.output_path

    def test_with_metadata(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
            include_metadata=True,
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        output_dir = Path(result.output_path)
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) == 3
        # Verificar contenido del metadata
        meta = json.loads(json_files[0].read_text())
        assert "page_index" in meta
        assert "ocr_text" in meta

    def test_missing_image(
        self, service: TransferService, tmp_path: Path,
    ):
        pages = [{"image_path": "/nonexistent/image.tiff", "page_index": 0}]
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
        )
        result = service.transfer(pages, config, batch_id=1)
        assert not result.success
        assert result.files_transferred == 0
        assert len(result.errors) == 1


# ------------------------------------------------------------------
# Transferencia a PDF
# ------------------------------------------------------------------


class TestPdfTransfer:
    def test_generate_pdf(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="pdf",
            destination=str(tmp_path / "output"),
            pdf_dpi=150,
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        assert result.success
        assert result.files_transferred == 3
        assert result.output_path.endswith(".pdf")

        # Verificar que el PDF tiene 3 páginas
        doc = pymupdf.open(result.output_path)
        assert len(doc) == 3
        doc.close()

    def test_generate_pdfa(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="pdfa",
            destination=str(tmp_path / "output"),
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        assert result.success
        assert result.output_path.endswith(".pdf")


# ------------------------------------------------------------------
# Transferencia CSV
# ------------------------------------------------------------------


class TestCsvTransfer:
    def test_generate_csv(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="csv",
            destination=str(tmp_path / "output"),
            csv_fields=["ref", "tipo"],
            csv_separator=";",
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        assert result.success
        assert result.output_path.endswith(".csv")

        # Leer y verificar el CSV
        with open(result.output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["ref"] == "REF-0"
        assert rows[0]["tipo"] == "factura"

    def test_csv_auto_detect_fields(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="csv",
            destination=str(tmp_path / "output"),
            csv_fields=[],  # Auto-detectar
        )
        result = service.transfer(sample_pages, config, batch_id=1)
        assert result.success

        with open(result.output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            rows = list(reader)

        assert "ref" in rows[0]
        assert "tipo" in rows[0]


# ------------------------------------------------------------------
# Modo no soportado
# ------------------------------------------------------------------


class TestUnsupportedMode:
    def test_unknown_mode(self, service: TransferService):
        config = TransferConfig(mode="ftp")
        result = service.transfer([], config)
        assert not result.success
        assert "no soportado" in result.errors[0]


# ------------------------------------------------------------------
# Filename pattern
# ------------------------------------------------------------------


class TestFilenamePattern:
    def test_custom_pattern(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
            filename_pattern="doc_{batch_id}_{page_index:04d}",
        )
        result = service.transfer(
            sample_pages[:1], config,
            batch_fields={"cliente": "ACME"}, batch_id=5,
        )
        output_dir = Path(result.output_path)
        files = list(output_dir.glob("doc_5_0000.*"))
        assert len(files) == 1

    def test_pattern_with_batch_fields(
        self, service: TransferService, sample_pages: list[dict],
        tmp_path: Path,
    ):
        config = TransferConfig(
            mode="folder",
            destination=str(tmp_path / "output"),
            filename_pattern="{cliente}_{page_index:04d}",
        )
        result = service.transfer(
            sample_pages[:1], config,
            batch_fields={"cliente": "ACME"}, batch_id=1,
        )
        output_dir = Path(result.output_path)
        files = list(output_dir.glob("ACME_0000.*"))
        assert len(files) == 1
