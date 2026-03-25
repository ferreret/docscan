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

    standard_enabled: bool = True  # False = solo on_transfer_advanced
    mode: str = "folder"  # "folder", "pdf", "pdfa", "csv"
    destination: str = ""  # Ruta destino o patrón
    filename_pattern: str = "{batch_id}_{page_index:04d}"
    create_subdirs: bool = True
    collision_policy: str = "suffix"  # "suffix", "overwrite", "merge"
    pdf_dpi: int = 200
    csv_separator: str = ";"
    csv_fields: list[str] = field(default_factory=list)
    include_metadata: bool = False

    # Formato de salida (modo carpeta)
    output_format: str = ""           # "" = original, "tiff", "png", "jpg", "pdf"
    output_dpi: int = 0               # 0 = original
    output_color_mode: str = ""       # "" = original, "color", "grayscale", "bw"
    output_jpeg_quality: int = 85
    output_tiff_compression: str = "lzw"
    output_png_compression: int = 6
    output_bw_threshold: int = 128

    # Calidad JPEG dentro del PDF
    pdf_jpeg_quality: int = 85


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
        on_page_callback: Any = None,
    ) -> TransferResult:
        """Ejecuta la transferencia de un lote.

        Args:
            pages: Lista de dicts con keys: image_path, page_index,
                   fields, ocr_text.
            config: Configuración de transferencia.
            batch_fields: Campos del lote (para interpolación).
            batch_id: ID del lote (para nombres de fichero).

        Returns:
            Resultado de la transferencia.
        """
        batch_fields = batch_fields or {}

        if config.mode == "folder":
            return self._transfer_folder(
                pages, config, batch_fields, batch_id, on_page_callback,
            )
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
        on_page_callback: Any = None,
    ) -> TransferResult:
        """Copia imágenes a una carpeta destino."""
        dest = Path(config.destination)
        if config.create_subdirs and batch_id is not None:
            dest = dest / f"batch_{batch_id}"
        dest.mkdir(parents=True, exist_ok=True)

        result = TransferResult(output_path=str(dest))
        needs_conversion = bool(config.output_format)

        for page in pages:
            try:
                src = Path(page["image_path"])
                if not src.exists():
                    result.errors.append(f"Imagen no encontrada: {src}")
                    continue

                # Determinar extensión destino
                if needs_conversion:
                    out_ext = f".{config.output_format.lower().strip('.')}"
                else:
                    out_ext = src.suffix

                filename = self._build_filename(
                    config.filename_pattern, page, batch_fields, batch_id,
                ) + out_ext
                dst = dest / filename
                dst.parent.mkdir(parents=True, exist_ok=True)

                dst = self._resolve_collision(
                    src, dst, config.collision_policy, needs_conversion, config,
                )
                if dst is not None:
                    if needs_conversion:
                        self._convert_and_save(src, dst, config)
                    else:
                        shutil.copy2(str(src), str(dst))

                result.files_transferred += 1

                if config.include_metadata:
                    self._write_metadata(dst, page)

                if on_page_callback:
                    on_page_callback(page.get("page_index", 0), True)

            except Exception as e:
                result.errors.append(f"Error copiando página {page.get('page_index')}: {e}")
                if on_page_callback:
                    on_page_callback(page.get("page_index", 0), False)

        result.success = len(result.errors) == 0
        log.info(
            "Transferencia carpeta: %d/%d ficheros a '%s'",
            result.files_transferred, len(pages), dest,
        )
        return result

    def _apply_output_transforms(
        self,
        img: np.ndarray,
        src: Path,
        config: TransferConfig,
    ) -> np.ndarray:
        """Aplica conversion de color y DPI segun config de salida."""
        from app.services.image_lib import ImageLib

        if config.output_color_mode == "grayscale":
            img = ImageLib.to_grayscale(img)
        elif config.output_color_mode == "bw":
            img = ImageLib.to_bw(img, config.output_bw_threshold)
        elif config.output_color_mode == "color":
            img = ImageLib.to_color(img)

        if config.output_dpi > 0:
            src_dpi = ImageLib.get_dpi(src)
            src_dpi_val = int(src_dpi[0]) if src_dpi[0] > 0 else 300
            if src_dpi_val != config.output_dpi:
                img = ImageLib.resize_to_dpi(img, src_dpi_val, config.output_dpi)

        return img

    def _convert_and_save(
        self,
        src: Path,
        dst: Path,
        config: TransferConfig,
    ) -> None:
        """Carga, convierte y guarda imagen segun config de salida."""
        from app.services.image_lib import ImageLib

        imgs = ImageLib.load(src)
        if not imgs:
            raise ValueError(f"No se pudo cargar: {src}")
        img = self._apply_output_transforms(imgs[0], src, config)

        ImageLib.save(
            img, dst,
            quality=config.output_jpeg_quality,
            compression=config.output_tiff_compression,
            png_level=config.output_png_compression,
            dpi=config.output_dpi if config.output_dpi > 0 else None,
        )

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
                encode_params = [
                    cv2.IMWRITE_JPEG_QUALITY, config.pdf_jpeg_quality,
                ]
                img_bytes = cv2.imencode(
                    ".jpg", img, encode_params,
                )[1].tobytes()
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
                index_fields = pages[0].get("fields", {})
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
                    index_fields = page_data.get("fields", {})
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

    _MAX_SUFFIX: int = 9999

    def _next_free_path(self, dst: Path) -> Path:
        """Devuelve la primera ruta libre anadiendo sufijo numerico."""
        stem, ext, parent = dst.stem, dst.suffix, dst.parent
        counter = 1
        while counter <= self._MAX_SUFFIX:
            candidate = parent / f"{stem}_{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1
        raise RuntimeError(
            f"No se encontro nombre libre para '{dst}' "
            f"tras {self._MAX_SUFFIX} intentos"
        )

    def _resolve_collision(
        self,
        src: Path,
        dst: Path,
        policy: str,
        needs_conversion: bool,
        config: TransferConfig,
    ) -> Path | None:
        """Resuelve la colision de nombre de fichero segun la politica.

        Returns:
            Path destino final, o None si el merge ya se encargo de la escritura.
        """
        if not dst.exists():
            return dst

        if policy == "overwrite":
            return dst

        if policy == "merge":
            return self._merge_into_existing(
                src, dst, needs_conversion, config,
            )

        return self._next_free_path(dst)

    def _merge_into_existing(
        self,
        src: Path,
        dst: Path,
        needs_conversion: bool,
        config: TransferConfig,
    ) -> Path | None:
        """Fusiona la imagen nueva con el fichero existente (multi-pagina).

        Returns:
            None si el merge se realizo, o Path si cayo en fallback a sufijo.
        """
        from app.services.image_lib import ImageLib

        ext = dst.suffix.lower()

        if ext == ".pdf":
            if needs_conversion:
                new_imgs = ImageLib.load(src)
                if not new_imgs:
                    raise ValueError(f"No se pudo cargar: {src}")
                img = self._apply_output_transforms(new_imgs[0], src, config)
                ImageLib.merge_to_pdf(
                    [img], dst, dpi=config.output_dpi or 200, append=True,
                )
            else:
                ImageLib.merge_to_pdf(
                    [src], dst, dpi=config.output_dpi or 200, append=True,
                )
            return None

        if ext in (".tif", ".tiff"):
            new_imgs = ImageLib.load(src)
            if not new_imgs:
                raise ValueError(f"No se pudo cargar: {src}")
            if needs_conversion:
                new_imgs = [self._apply_output_transforms(new_imgs[0], src, config)]
            existing = ImageLib.load(str(dst))
            ImageLib.merge_to_tiff(
                existing + new_imgs, str(dst),
                compression=config.output_tiff_compression,
                dpi=config.output_dpi if config.output_dpi > 0 else None,
            )
            return None

        # Formatos sin multi-pagina: fallback a sufijo
        candidate = self._next_free_path(dst)
        if needs_conversion:
            new_imgs = ImageLib.load(src)
            if not new_imgs:
                raise ValueError(f"No se pudo cargar: {src}")
            img = self._apply_output_transforms(new_imgs[0], src, config)
            ImageLib.save(img, candidate)
        else:
            shutil.copy2(str(src), str(candidate))
        return None

    def _build_filename(
        self,
        pattern: str,
        page: dict[str, Any],
        batch_fields: dict[str, str],
        batch_id: int | None,
    ) -> str:
        """Construye un nombre de fichero interpolando variables.

        Las claves de batch_fields se normalizan: espacios → guiones bajos,
        para que "fecha lote" sea accesible como {fecha_lote}.
        """
        # Normalizar claves: "fecha lote" → "fecha_lote"
        normalized = {
            k.replace(" ", "_"): v for k, v in batch_fields.items()
        }
        try:
            result = pattern.format(
                batch_id=batch_id or 0,
                page_index=page.get("page_index", 0),
                first_barcode=page.get("first_barcode", ""),
                **normalized,
            )
        except (KeyError, IndexError, ValueError) as e:
            log.warning(
                "Error interpolando patrón '%s': %s. "
                "Variables: batch_id=%s, page_index=%s, first_barcode=%s, campos=%s",
                pattern, e, batch_id, page.get("page_index"),
                page.get("first_barcode"), list(normalized.keys()),
            )
            result = f"batch_{batch_id or 0}_page_{page.get('page_index', 0):04d}"

        # Sanitizar path traversal: reemplazar separadores sospechosos
        result = result.replace("\\", "_")
        # Permitir "/" como separador de subdirectorios intencionado
        # pero verificar que no haya ".." para evitar traversal
        parts = result.split("/")
        parts = [p for p in parts if p != ".."]
        return "/".join(parts)

    def _write_metadata(self, image_path: Path, page: dict[str, Any]) -> None:
        """Escribe un fichero .json de metadatos junto a la imagen."""
        meta_path = image_path.with_suffix(".json")
        metadata = {
            "page_index": page.get("page_index"),
            "ocr_text": page.get("ocr_text", ""),
            "fields": page.get("fields", {}),
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
