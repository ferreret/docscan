"""Servicio de importación de imágenes y PDFs.

Soporta:
- Imágenes individuales (TIFF, JPEG, PNG, BMP)
- Carpetas completas de imágenes
- PDFs (cada página extraída como imagen a DPI configurable)
- TIFFs multipágina
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import pymupdf

log = logging.getLogger(__name__)

# Extensiones soportadas
IMAGE_EXTENSIONS = {".tiff", ".tif", ".jpeg", ".jpg", ".png", ".bmp"}
PDF_EXTENSIONS = {".pdf"}
ALL_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS

DEFAULT_DPI = 300


class ImportService:
    """Servicio de importación de imágenes y PDFs.

    Args:
        default_dpi: DPI para renderizar páginas de PDF (default 300).
    """

    def __init__(self, default_dpi: int = DEFAULT_DPI) -> None:
        self._default_dpi = default_dpi

    def import_file(
        self, path: Path | str, dpi: int | None = None,
    ) -> list[np.ndarray]:
        """Importa un fichero (imagen o PDF).

        Args:
            path: Ruta al fichero.
            dpi: DPI para PDFs (usa default si no se indica).

        Returns:
            Lista de imágenes (una por página).

        Raises:
            FileNotFoundError: Si el fichero no existe.
            ValueError: Si el formato no está soportado.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Fichero no encontrado: {path}")

        suffix = path.suffix.lower()
        dpi = dpi or self._default_dpi

        if suffix in PDF_EXTENSIONS:
            return self._import_pdf(path, dpi)
        elif suffix in (".tiff", ".tif"):
            return self._import_tiff(path)
        elif suffix in IMAGE_EXTENSIONS:
            return self._import_image(path)
        else:
            raise ValueError(
                f"Formato no soportado: '{suffix}'. "
                f"Formatos válidos: {sorted(ALL_EXTENSIONS)}"
            )

    def import_folder(
        self,
        folder: Path | str,
        dpi: int | None = None,
        recursive: bool = False,
    ) -> list[np.ndarray]:
        """Importa todas las imágenes y PDFs de una carpeta.

        Args:
            folder: Ruta a la carpeta.
            dpi: DPI para PDFs.
            recursive: Si busca en subcarpetas.

        Returns:
            Lista de imágenes en orden alfabético de fichero.
        """
        folder = Path(folder)
        if not folder.is_dir():
            raise NotADirectoryError(f"No es una carpeta: {folder}")

        pattern = "**/*" if recursive else "*"
        files = sorted(
            f for f in folder.glob(pattern)
            if f.is_file() and f.suffix.lower() in ALL_EXTENSIONS
        )

        images: list[np.ndarray] = []
        for f in files:
            try:
                images.extend(self.import_file(f, dpi))
            except Exception as e:
                log.error("Error importando '%s': %s", f, e)

        log.info(
            "Importadas %d imágenes de %d ficheros en '%s'",
            len(images), len(files), folder,
        )
        return images

    def get_supported_extensions(self) -> list[str]:
        """Devuelve las extensiones soportadas."""
        return sorted(ALL_EXTENSIONS)

    # ------------------------------------------------------------------
    # Importadores específicos
    # ------------------------------------------------------------------

    def _import_pdf(self, path: Path, dpi: int) -> list[np.ndarray]:
        """Extrae cada página de un PDF como imagen."""
        images: list[np.ndarray] = []
        doc = pymupdf.open(str(path))

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=dpi)

                # Pixmap a numpy array
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n,
                )

                # Convertir RGB a BGR para OpenCV
                if pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                elif pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
                elif pix.n == 1:
                    pass  # Gris, no necesita conversión

                images.append(img.copy())

            log.info("PDF '%s': %d páginas a %d DPI", path.name, len(images), dpi)
        finally:
            doc.close()

        return images

    def _import_tiff(self, path: Path) -> list[np.ndarray]:
        """Importa TIFF (soporta multipágina)."""
        images: list[np.ndarray] = []

        # Intentar con OpenCV primero (multipágina)
        success, frames = cv2.imreadmulti(str(path))
        if success and frames:
            for frame in frames:
                images.append(frame)
            log.info(
                "TIFF '%s': %d páginas", path.name, len(images),
            )
            return images

        # Fallback: lectura simple
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is not None:
            return [img]

        raise ValueError(f"No se pudo leer el TIFF: {path}")

    def _import_image(self, path: Path) -> list[np.ndarray]:
        """Importa una imagen individual."""
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"No se pudo leer la imagen: {path}")
        return [img]
