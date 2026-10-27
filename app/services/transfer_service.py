"""Servicio de transferencia de lotes.

Copia/mueve las imágenes y metadatos del lote al destino configurado.
Soporta múltiples modos: copia a carpeta, PDF, PDF/A, CSV, y
transferencia avanzada por script.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np
import pymupdf

from app.models.document import LogicalDocument, split_documents

log = logging.getLogger(__name__)

# Saneado de rutas (paridad con FlexibarNET10 v1.26: SanitizeRelativePath +
# IsUnderDestFolder). Los valores interpolados salen del papel (barcodes,
# OCR, IA) y no son de confianza.
_INVALID_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
MAX_SEGMENT_LENGTH = 200


class UnsafePathError(ValueError):
    """La ruta calculada saldría de la carpeta de destino."""


def sanitize_value(value: Any) -> Any:
    """Neutraliza un valor que se va a interpolar en un nombre de fichero.

    Las barras de un valor nunca crean subcarpetas: solo lo hacen las que
    escribe el usuario en el patrón. Los no-texto (índices, ids) se
    devuelven tal cual para que sigan admitiendo formato (``:04d``).
    """
    if not isinstance(value, str):
        return value
    return value.replace("/", "_").replace("\\", "_")


def sanitize_segment(segment: str) -> str:
    """Convierte un segmento de ruta en un nombre válido en Windows y Linux.

    Sustituye caracteres no válidos, quita puntos y espacios finales,
    protege los nombres reservados de Windows (``CON``, ``NUL``, ``COM1``…)
    y limita la longitud a ``MAX_SEGMENT_LENGTH``. Devuelve ``""`` para los
    segmentos que no deben existir (vacíos, ``.`` y ``..``).
    """
    cleaned = _INVALID_PATH_CHARS.sub("_", segment).strip().rstrip(". ")
    if cleaned in ("", ".", ".."):
        return ""
    if cleaned.split(".", 1)[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned[:MAX_SEGMENT_LENGTH]


def safe_join(dest: Path, relative: str) -> Path:
    """Une ``relative`` a ``dest`` garantizando que no sale de ella.

    Raises:
        UnsafePathError: Si la ruta resultante queda fuera de ``dest``.
    """
    target = (dest / relative).resolve()
    if not target.is_relative_to(dest.resolve()):
        raise UnsafePathError(
            f"La ruta '{relative}' queda fuera de la carpeta de destino"
        )
    return target


@dataclass
class TransferConfig:
    """Configuración de transferencia de una aplicación.

    Se deserializa desde ``Application.transfer_json``.
    """

    standard_enabled: bool = True  # False = solo on_transfer_advanced
    # "folder" (un fichero por página), "pdf", "pdfa", "tiff" (multipágina), "csv"
    mode: str = "folder"
    destination: str = ""  # Ruta destino o patrón
    filename_pattern: str = "{batch_id}_{page_index:04d}"
    # Nombre del fichero: "pattern" (filename_pattern) o "script"
    # (file_name_script). Mismas claves que FlexibarNET10.
    name_mode: str = "pattern"
    file_name_script: str = ""
    # Multipágina (pdf, pdfa, tiff): "batch" = un fichero por lote,
    # "document" = uno por documento (tramo entre separadores).
    grouping: str = "batch"
    # La página separadora es la portada del documento ("include") o una
    # hoja separadora que no se transfiere ("exclude").
    separator_page: str = "include"
    create_subdirs: bool = True
    collision_policy: str = "suffix"  # "suffix", "overwrite", "merge"
    pdf_dpi: int = 200
    csv_separator: str = ";"
    csv_fields: list[str] = field(default_factory=list)
    include_metadata: bool = False

    # Formato de salida (modo carpeta)
    output_format: str = ""  # "" = original, "tiff", "png", "jpg", "pdf"
    output_dpi: int = 0  # 0 = original
    output_color_mode: str = ""  # "" = original, "color", "grayscale", "bw"
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
    # Como FlexibarNET10: una config sin name_mode pero con script de nombre
    # quería usar el script.
    if "name_mode" not in data and str(data.get("file_name_script", "")).strip():
        data["name_mode"] = "script"
    return TransferConfig(
        **{k: v for k, v in data.items() if k in TransferConfig.__dataclass_fields__}
    )


MULTIPAGE_MODES = ("pdf", "pdfa", "tiff")

# Resuelve el nombre de un fichero por script: recibe la página y su
# documento y devuelve la subruta sin extensión, o None/"" para usar el patrón.
NameResolver = Callable[[dict[str, Any], LogicalDocument | None], str | None]


class TransferAbortedError(Exception):
    """La transferencia no puede empezar: no se ha escrito nada."""


def _uses_token(pattern: str, token: str) -> bool:
    return "{" + token + "}" in pattern or "{" + token + ":" in pattern


def missing_images(pages: list[dict[str, Any]]) -> list[int]:
    """Índices de las páginas cuya imagen no está en disco."""
    return [
        page.get("page_index", 0)
        for page in pages
        if not Path(page.get("image_path") or "").is_file()
    ]


def document_problems(
    pages: list[dict[str, Any]], config: TransferConfig
) -> str | None:
    """Comprueba los documentos del lote antes de transferir.

    Returns:
        None si se puede transferir, o el motivo por el que no.
    """
    documents = split_documents(pages)
    exclude = config.separator_page == "exclude"
    has_separators = any(not d.is_implicit for d in documents)

    if exclude and has_separators and documents and documents[0].is_implicit:
        return (
            f"Hay {len(documents[0].pages)} página(s) antes de la primera hoja "
            "separadora: no pertenecen a ningún documento"
        )
    if exclude:
        for doc in documents:
            if not doc.is_implicit and len(doc.pages) == 1:
                return (
                    f"El documento {doc.index} ({doc.separator_value or 'sin valor'}) "
                    "solo tiene la hoja separadora: quedaría vacío"
                )
    if config.name_mode != "script" and _uses_token(
        config.filename_pattern, "separator"
    ):
        for doc in documents:
            if not doc.separator_value:
                return (
                    f"El documento {doc.index} no tiene valor de separador y el "
                    "nombre del fichero usa {separator}: los ficheros se pisarían"
                )
    return None


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
        name_resolver: NameResolver | None = None,
    ) -> TransferResult:
        """Ejecuta la transferencia de un lote.

        Antes de escribir nada se comprueban los documentos y se calculan
        todos los nombres: si falla cualquiera (por ejemplo, el script de
        nombre lanza), la transferencia no empieza y no queda salida a medias.

        Args:
            pages: Lista de dicts con keys: image_path, page_index,
                   fields, ocr_text, is_separator, separator_value.
            config: Configuración de transferencia.
            batch_fields: Campos del lote (para interpolación).
            batch_id: ID del lote (para nombres de fichero).
            on_page_callback: ``(page_index, success)`` por página.
            name_resolver: Script de nombre ya preparado (``name_mode``
                ``"script"``).

        Returns:
            Resultado de la transferencia.
        """
        batch_fields = batch_fields or {}

        if config.mode in ("folder", *MULTIPAGE_MODES):
            if not pages:
                return TransferResult(
                    success=False, errors=["No hay páginas que transferir"]
                )
            problem = document_problems(pages, config)
            if problem:
                return TransferResult(success=False, errors=[problem])
            # Una imagen que falta se detecta antes de escribir nada: un
            # fallo a mitad dejaría salida parcial y, con «Fusionar», el
            # reintento anexaría otra vez las páginas ya archivadas.
            missing = missing_images(pages)
            if missing:
                return TransferResult(
                    success=False,
                    errors=[
                        "Faltan las imágenes de las páginas "
                        + ", ".join(str(i + 1) for i in missing[:10])
                        + ("…" if len(missing) > 10 else "")
                    ],
                )

        try:
            if config.mode == "folder":
                return self._transfer_folder(
                    pages,
                    config,
                    batch_fields,
                    batch_id,
                    on_page_callback,
                    name_resolver,
                )
            if config.mode in MULTIPAGE_MODES:
                return self._transfer_multipage(
                    pages,
                    config,
                    batch_fields,
                    batch_id,
                    on_page_callback,
                    name_resolver,
                )
        except TransferAbortedError as e:
            return TransferResult(success=False, errors=[str(e)])

        if config.mode == "csv":
            return self._transfer_csv(pages, config, batch_fields, batch_id)
        return TransferResult(
            success=False,
            errors=[f"Modo de transferencia no soportado: '{config.mode}'"],
        )

    # ------------------------------------------------------------------
    # Documentos y nombres
    # ------------------------------------------------------------------

    @staticmethod
    def _document_of(
        pages: list[dict[str, Any]],
    ) -> tuple[list[LogicalDocument], dict[int, LogicalDocument]]:
        """Documentos del lote y mapa ``id(página) -> documento``."""
        documents = split_documents(pages)
        by_page = {id(page): doc for doc in documents for page in doc.pages}
        return documents, by_page

    @staticmethod
    def _output_pages(
        document: LogicalDocument,
        config: TransferConfig,
    ) -> list[dict[str, Any]]:
        """Páginas del documento que se transfieren."""
        if config.separator_page == "exclude" and not document.is_implicit:
            return document.pages[1:]
        return list(document.pages)

    def _resolve_name(
        self,
        config: TransferConfig,
        page: dict[str, Any],
        document: LogicalDocument | None,
        batch_fields: dict[str, str],
        batch_id: int | None,
        name_resolver: NameResolver | None,
    ) -> str:
        """Subruta y nombre (sin extensión) de un fichero de salida.

        Con ``name_mode="script"`` manda el script; si devuelve vacío o None
        se usa el patrón, como en FlexibarNET10. A diferencia de Flexibar,
        si el script **lanza** la transferencia no se hace: un error de
        script nunca se da por bueno.

        Raises:
            TransferAbortedError: Si el script de nombre falla.
        """
        if config.name_mode == "script" and name_resolver is not None:
            try:
                relative = name_resolver(page, document)
            except Exception as e:
                raise TransferAbortedError(
                    f"Ha fallado el script de nombre en la página "
                    f"{page.get('page_index', 0) + 1}: {e}"
                ) from e
            if isinstance(relative, str) and relative.strip():
                return self._sanitize_relative(relative)
            log.warning(
                "El script de nombre no devolvió nada para la página %s: "
                "se usa el patrón",
                page.get("page_index"),
            )
        return self._build_filename(
            config.filename_pattern,
            page,
            batch_fields,
            batch_id,
            document,
        )

    @staticmethod
    def _sanitize_relative(relative: str) -> str:
        """Sanea cada segmento de una subruta (las "/" crean subcarpetas)."""
        segments = [
            sanitize_segment(part) for part in relative.replace("\\", "/").split("/")
        ]
        return "/".join(part for part in segments if part)

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
        name_resolver: NameResolver | None = None,
    ) -> TransferResult:
        """Copia imágenes a una carpeta destino (un fichero por página)."""
        dest = Path(config.destination)
        if config.create_subdirs and batch_id is not None:
            dest = dest / f"batch_{batch_id}"

        documents, by_page = self._document_of(pages)
        needs_conversion = bool(config.output_format)

        # Nombres primero: si alguno falla no se escribe nada.
        planned: list[tuple[dict[str, Any], str]] = []
        for document in documents:
            for page in self._output_pages(document, config):
                name = self._resolve_name(
                    config,
                    page,
                    by_page.get(id(page)),
                    batch_fields,
                    batch_id,
                    name_resolver,
                )
                planned.append((page, name))

        for page, name in planned:
            try:
                safe_join(dest, name)
            except UnsafePathError as e:
                raise TransferAbortedError(str(e)) from e

        dest.mkdir(parents=True, exist_ok=True)
        result = TransferResult(output_path=str(dest))

        for page, name in planned:
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

                dst = safe_join(dest, name + out_ext)
                dst.parent.mkdir(parents=True, exist_ok=True)

                dst = self._resolve_collision(
                    src,
                    dst,
                    config.collision_policy,
                    needs_conversion,
                    config,
                )
                if dst is not None:
                    if needs_conversion:
                        self._convert_and_save(src, dst, config)
                    else:
                        shutil.copy2(str(src), str(dst))

                result.files_transferred += 1

                if config.include_metadata and dst is not None:
                    self._write_metadata(dst, page)

                if on_page_callback:
                    on_page_callback(page.get("page_index", 0), True)

            except Exception as e:
                result.errors.append(
                    f"Error copiando página {page.get('page_index')}: {e}"
                )
                if on_page_callback:
                    on_page_callback(page.get("page_index", 0), False)

        result.success = len(result.errors) == 0
        log.info(
            "Transferencia carpeta: %d/%d ficheros a '%s'",
            result.files_transferred,
            len(planned),
            dest,
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
            img,
            dst,
            quality=config.output_jpeg_quality,
            compression=config.output_tiff_compression,
            png_level=config.output_png_compression,
            dpi=config.output_dpi if config.output_dpi > 0 else None,
        )

    # ------------------------------------------------------------------
    # Transferencia multipágina (PDF, PDF/A, TIFF)
    # ------------------------------------------------------------------

    def _transfer_multipage(
        self,
        pages: list[dict[str, Any]],
        config: TransferConfig,
        batch_fields: dict[str, str],
        batch_id: int | None,
        on_page_callback: Any = None,
        name_resolver: NameResolver | None = None,
    ) -> TransferResult:
        """Un fichero multipágina por lote o por documento.

        Con la colisión ``merge`` el fichero existente crece por el final:
        las páginas no consecutivas con el mismo nombre acaban juntas
        (AppendToEnd de FlexibarNET10).
        """
        dest = Path(config.destination)
        ext = ".tif" if config.mode == "tiff" else ".pdf"
        documents, _ = self._document_of(pages)

        # Unidades: (páginas a escribir, documento que da el nombre)
        units: list[tuple[list[dict[str, Any]], LogicalDocument | None]] = []
        if config.grouping == "document":
            for document in documents:
                units.append((self._output_pages(document, config), document))
        else:
            out = [p for d in documents for p in self._output_pages(d, config)]
            units.append((out, documents[0] if documents else None))
        units = [(u, d) for u, d in units if u]

        # Nombres primero: si alguno falla no se escribe nada.
        planned: list[tuple[list[dict[str, Any]], Path]] = []
        for unit_pages, document in units:
            first = document.pages[0] if document else unit_pages[0]
            name = self._resolve_name(
                config, first, document, batch_fields, batch_id, name_resolver
            )
            try:
                planned.append((unit_pages, safe_join(dest, name + ext)))
            except UnsafePathError as e:
                raise TransferAbortedError(str(e)) from e

        dest.mkdir(parents=True, exist_ok=True)
        result = TransferResult(
            output_path=str(planned[0][1] if len(planned) == 1 else dest)
        )

        for unit_pages, path in planned:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                append = False
                if path.exists():
                    if config.collision_policy == "merge":
                        append = True
                    elif config.collision_policy != "overwrite":
                        path = self._next_free_path(path)
                result.files_transferred += self._write_multipage(
                    unit_pages, path, config, append
                )
                ok = True
            except Exception as e:
                ok = False
                result.errors.append(f"Error generando '{path.name}': {e}")
            if on_page_callback:
                for page in unit_pages:
                    on_page_callback(page.get("page_index", 0), ok)

        result.success = len(result.errors) == 0
        log.info(
            "Transferencia %s: %d páginas en %d fichero(s) → '%s'",
            config.mode,
            result.files_transferred,
            len(planned),
            dest,
        )
        return result

    def _write_multipage(
        self,
        unit_pages: list[dict[str, Any]],
        path: Path,
        config: TransferConfig,
        append: bool,
    ) -> int:
        """Escribe (o amplía) un PDF o TIFF multipágina de forma atómica.

        Se escribe en un temporal junto al destino y se renombra: un fallo a
        mitad no deja un fichero corrupto ni pierde lo que ya tenía.

        Returns:
            Número de páginas escritas.
        """
        from app.services.image_lib import ImageLib

        images: list[np.ndarray] = []
        source_dpi = 0
        for page in unit_pages:
            src = Path(page["image_path"])
            loaded = ImageLib.load(src) if src.exists() else []
            if not loaded:
                # Nunca un fichero con menos páginas de las debidas.
                raise ValueError(f"no se pudo leer la imagen {src.name}")
            if not source_dpi:
                source_dpi = int(ImageLib.get_dpi(src)[0] or 0)
            images.append(self._apply_output_transforms(loaded[0], src, config))

        tmp = path.with_name(f".{path.name}.tmp")
        try:
            if config.mode == "tiff":
                existing = ImageLib.load(str(path)) if append else []
                ImageLib.merge_to_tiff(
                    existing + images,
                    tmp,
                    compression=config.output_tiff_compression,
                    dpi=config.output_dpi or source_dpi or None,
                )
            else:
                self._write_pdf(images, path, tmp, config, append)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        log.info(
            "%s: %d página(s) %s",
            path,
            len(images),
            "añadidas al final" if append else "escritas",
        )
        return len(images)

    def _write_pdf(
        self,
        images: list[np.ndarray],
        path: Path,
        tmp: Path,
        config: TransferConfig,
        append: bool,
    ) -> None:
        """Escribe las imágenes en un PDF (ampliando ``path`` si ``append``)."""
        doc = pymupdf.open(str(path)) if append else pymupdf.open()
        try:
            for img in images:
                h, w = img.shape[:2]
                page_w = w * 72.0 / config.pdf_dpi
                page_h = h * 72.0 / config.pdf_dpi
                pdf_page = doc.new_page(width=page_w, height=page_h)
                img_bytes = cv2.imencode(
                    ".jpg",
                    img,
                    [cv2.IMWRITE_JPEG_QUALITY, config.pdf_jpeg_quality],
                )[1].tobytes()
                pdf_page.insert_image(
                    pymupdf.Rect(0, 0, page_w, page_h),
                    stream=img_bytes,
                )
            if config.mode == "pdfa":
                doc.scrub()
            doc.save(str(tmp))
        finally:
            doc.close()

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

        filename = (
            self._build_filename(
                config.filename_pattern,
                pages[0] if pages else {},
                batch_fields,
                batch_id,
            )
            + ".csv"
        )
        try:
            output_path = safe_join(dest, filename)
        except UnsafePathError as e:
            return TransferResult(success=False, errors=[str(e)])

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
                    f,
                    fieldnames=headers,
                    delimiter=config.csv_separator,
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
                result.files_transferred,
                output_path,
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
            f"No se encontro nombre libre para '{dst}' tras {self._MAX_SUFFIX} intentos"
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
                src,
                dst,
                needs_conversion,
                config,
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
                    [img],
                    dst,
                    dpi=config.output_dpi or 200,
                    append=True,
                )
            else:
                ImageLib.merge_to_pdf(
                    [src],
                    dst,
                    dpi=config.output_dpi or 200,
                    append=True,
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
                existing + new_imgs,
                str(dst),
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
        document: LogicalDocument | None = None,
    ) -> str:
        """Construye un nombre de fichero interpolando variables.

        Las claves de batch_fields se normalizan: espacios → guiones bajos,
        para que "fecha lote" sea accesible como {fecha_lote}.

        Los tokens de documento (``{separator}``, ``{document_index}`` y su
        alias ``{document_id}``) se resuelven sobre el documento de la
        página, también en las páginas que no son la separadora. Flexibar
        dejaba ``{separator}`` vacío en ellas, en contra de su manual.
        """
        # Normalizar claves: "fecha lote" → "fecha_lote"
        normalized = {
            k.replace(" ", "_"): sanitize_value(v) for k, v in batch_fields.items()
        }
        fallback = f"batch_{batch_id or 0}_page_{page.get('page_index', 0):04d}"
        # Las variables del sistema ganan a un campo de lote con el mismo
        # nombre (antes, un campo «batch_id» hacía fallar la transferencia).
        values = {
            **normalized,
            "batch_id": batch_id or 0,
            "page_index": page.get("page_index", 0),
            "first_barcode": sanitize_value(page.get("first_barcode", "")),
            "separator": sanitize_value(document.separator_value if document else ""),
            "document_index": document.index if document else 0,
            "document_id": document.index if document else 0,
        }
        try:
            result = pattern.format_map(values)
        except (KeyError, IndexError, ValueError) as e:
            log.warning(
                "Error interpolando patrón '%s': %s. "
                "Variables: batch_id=%s, page_index=%s, campos=%s",
                pattern,
                e,
                batch_id,
                page.get("page_index"),
                list(normalized.keys()),
            )
            return fallback

        # Las "/" que quedan son las del patrón: subcarpetas intencionadas.
        # "\\" se trata igual para que un patrón escrito en Windows funcione.
        segments = [sanitize_segment(p) for p in result.replace("\\", "/").split("/")]
        segments = [p for p in segments if p]
        return "/".join(segments) or fallback

    def _write_metadata(self, image_path: Path, page: dict[str, Any]) -> None:
        """Escribe un fichero .json de metadatos junto a la imagen."""
        meta_path = image_path.with_suffix(".json")
        metadata = {
            "page_index": page.get("page_index"),
            "ocr_text": page.get("ocr_text", ""),
            "fields": page.get("fields", {}),
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
