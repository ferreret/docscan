"""Servicio de transferencia de lotes.

Copia/mueve las imágenes y metadatos del lote al destino configurado.
Soporta múltiples modos: copia a carpeta, PDF, PDF/A, CSV, y
transferencia avanzada por script.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pymupdf

log = logging.getLogger(__name__)


@dataclass
class TransferConfig:
    """Configuración de transferencia de una aplicación.

    Se deserializa desde ``Application.transfer_json``.
    """

    mode: str = "folder"  # "folder", "pdf", "pdfa", "csv", "script"
    destination: str = ""  # Ruta destino o patrón
    filename_pattern: str = "{batch_id}_{page_index:04d}"
    create_subdirs: bool = True
    pdf_dpi: int = 200
    csv_separator: str = ";"
    csv_fields: list[str] = field(default_factory=list)
    include_metadata: bool = False


def parse_transfer_config(json_str: str) -> TransferConfig:
    """Parsea la configuración de transferencia desde JSON."""
    if not json_str or json_str == "{}":
        return TransferConfig()
    data = json.loads(json_str)
    return TransferConfig(**{
        k: v for k, v in data.items()
        if k in TransferConfig.__dataclass_fields__
    })


@dataclass
class TransferResult:
    """Resultado de una transferencia."""

    success: bool = True
    files_transferred: int = 0
    output_path: str = ""
    errors: list[str] = field(default_factory=list)


class TransferService:
    """Servicio de transferencia de lotes procesados."""

    def transfer(
        self,
        pages: list[dict[str, Any]],
        config: TransferConfig,
        batch_fields: dict[str, str] | None = None,
        batch_id: int | None = None,
    ) -> TransferResult:
        """Ejecuta la transferencia de un lote.

        Args:
            pages: Lista de dicts con keys: image_path, page_index,
                   index_fields, ocr_text, ai_fields.
            config: Configuración de transferencia.
            batch_fields: Campos del lote (para interpolación).
            batch_id: ID del lote (para nombres de fichero).

        Returns:
            Resultado de la transferencia.
        """
        batch_fields = batch_fields or {}

        if config.mode == "folder":
            return self._transfer_folder(pages, config, batch_fields, batch_id)
        elif config.mode in ("pdf", "pdfa"):
            return self._transfer_pdf(pages, config, batch_fields, batch_id)
        elif config.mode == "csv":
            return self._transfer_csv(pages, config, batch_fields, batch_id)
        else:
            return TransferResult(
                success=False,
                errors=[f"Modo de transferencia no soportado: '{config.mode}'"],
            )

    # ------------------------------------------------------------------
    # Transferencia a carpeta
    # ------------------------------------------------------------------

    def _transfer_folder(
        self,
        pages: list[dict[str, Any]],
        config: TransferConfig,
        batch_fields: dict[str, str],
        batch_id: int | None,
    ) -> TransferResult:
        """Copia imágenes a una carpeta destino."""
        dest = Path(config.destination)
        if config.create_subdirs and batch_id is not None:
            dest = dest / f"batch_{batch_id}"
        dest.mkdir(parents=True, exist_ok=True)

        result = TransferResult(output_path=str(dest))

        for page in pages:
            try:
                src = Path(page["image_path"])
                if not src.exists():
                    result.errors.append(f"Imagen no encontrada: {src}")
                    continue

                filename = self._build_filename(
                    config.filename_pattern, page, batch_fields, batch_id,
                ) + src.suffix
                dst = dest / filename

                shutil.copy2(str(src), str(dst))
                result.files_transferred += 1

                if config.include_metadata:
                    self._write_metadata(dst, page)

            except Exception as e:
                result.errors.append(f"Error copiando página {page.get('page_index')}: {e}")

        result.success = len(result.errors) == 0
        log.info(
            "Transferencia carpeta: %d/%d ficheros a '%s'",
            result.files_transferred, len(pages), dest,
        )
        return result

    # ------------------------------------------------------------------
    # Transferencia a PDF
    # ------------------------------------------------------------------

    def _transfer_pdf(
        self,
        pages: list[dict[str, Any]],
        config: TransferConfig,
        batch_fields: dict[str, str],
        batch_id: int | None,
    ) -> TransferResult:
        """Genera un PDF con todas las páginas del lote."""
        dest = Path(config.destination)
        dest.mkdir(parents=True, exist_ok=True)

        filename = self._build_filename(
            config.filename_pattern, pages[0] if pages else {},
            batch_fields, batch_id,
        ) + ".pdf"
        output_path = dest / filename

        result = TransferResult(output_path=str(output_path))
        doc = pymupdf.open()

        try:
            for page_data in pages:
                src = Path(page_data["image_path"])
                if not src.exists():
                    result.errors.append(f"Imagen no encontrada: {src}")
                    continue

                img = cv2.imread(str(src), cv2.IMREAD_COLOR)
                if img is None:
                    result.errors.append(f"No se pudo leer: {src}")
                    continue

                # Convertir BGR a RGB para pymupdf
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = img_rgb.shape[:2]

                # Calcular tamaño de página en puntos (72 DPI base)
                page_w = w * 72.0 / config.pdf_dpi
                page_h = h * 72.0 / config.pdf_dpi

                pdf_page = doc.new_page(width=page_w, height=page_h)

                # Insertar imagen
                img_bytes = cv2.imencode(".jpg", img)[1].tobytes()
                pdf_page.insert_image(
                    pymupdf.Rect(0, 0, page_w, page_h),
                    stream=img_bytes,
                )
                result.files_transferred += 1

            if config.mode == "pdfa":
                doc.scrub()

            doc.save(str(output_path))
            result.success = len(result.errors) == 0

            log.info(
                "Transferencia PDF: %d páginas → '%s'",
                result.files_transferred, output_path,
            )
        except Exception as e:
            result.success = False
            result.errors.append(f"Error generando PDF: {e}")
        finally:
            doc.close()

        return result

    # ------------------------------------------------------------------
    # Transferencia CSV
    # ------------------------------------------------------------------

    def _transfer_csv(
        self,
        pages: list[dict[str, Any]],
        config: TransferConfig,
        batch_fields: dict[str, str],
        batch_id: int | None,
    ) -> TransferResult:
        """Genera un CSV con los campos indexados de cada página."""
        dest = Path(config.destination)
        dest.mkdir(parents=True, exist_ok=True)

        filename = self._build_filename(
            config.filename_pattern, pages[0] if pages else {},
            batch_fields, batch_id,
        ) + ".csv"
        output_path = dest / filename

        result = TransferResult(output_path=str(output_path))

        # Determinar columnas
        csv_fields = config.csv_fields
        if not csv_fields:
            # Auto-detectar de los campos indexados de la primera página
            if pages:
                index_fields = pages[0].get("index_fields", {})
                csv_fields = list(index_fields.keys())

        headers = ["page_index", "image_path"] + csv_fields

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=headers, delimiter=config.csv_separator,
                    extrasaction="ignore",
                )
                writer.writeheader()

                for page_data in pages:
                    row = {
                        "page_index": page_data.get("page_index", ""),
                        "image_path": page_data.get("image_path", ""),
                    }
                    index_fields = page_data.get("index_fields", {})
                    for field_name in csv_fields:
                        row[field_name] = index_fields.get(field_name, "")

                    writer.writerow(row)
                    result.files_transferred += 1

            result.success = True
            log.info(
                "Transferencia CSV: %d filas → '%s'",
                result.files_transferred, output_path,
            )
        except Exception as e:
            result.success = False
            result.errors.append(f"Error generando CSV: {e}")

        return result

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _build_filename(
        self,
        pattern: str,
        page: dict[str, Any],
        batch_fields: dict[str, str],
        batch_id: int | None,
    ) -> str:
        """Construye un nombre de fichero interpolando variables."""
        try:
            return pattern.format(
                batch_id=batch_id or 0,
                page_index=page.get("page_index", 0),
                **batch_fields,
            )
        except (KeyError, IndexError, ValueError):
            # Fallback seguro
            return f"batch_{batch_id or 0}_page_{page.get('page_index', 0):04d}"

    def _write_metadata(self, image_path: Path, page: dict[str, Any]) -> None:
        """Escribe un fichero .json de metadatos junto a la imagen."""
        meta_path = image_path.with_suffix(".json")
        metadata = {
            "page_index": page.get("page_index"),
            "ocr_text": page.get("ocr_text", ""),
            "ai_fields": page.get("ai_fields", {}),
            "index_fields": page.get("index_fields", {}),
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
