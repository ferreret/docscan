"""ImageLib — Librería de tratamiento de imágenes.

Clase con métodos estáticos para lectura, escritura, conversión,
merge/split, DPI y modo de color. Sin dependencias de servicios.
Disponible desde cualquier Script/Evento.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

log = logging.getLogger(__name__)

# Mapeo de compresión TIFF para Pillow
_TIFF_COMPRESSION = {
    "none": None,
    "lzw": "tiff_lzw",
    "zip": "tiff_deflate",
    "group4": "group4",
}


class ImageLib:
    """Librería de tratamiento de imágenes con métodos estáticos.

    Disponible en scripts y eventos como ``ImageLib``.
    """

    # ------------------------------------------------------------------
    # Lectura / Escritura
    # ------------------------------------------------------------------

    @staticmethod
    def load(path: str | Path) -> list[np.ndarray]:
        """Carga imagen(es). PDF y TIFF multipágina devuelven lista.

        Args:
            path: Ruta al fichero.

        Returns:
            Lista de imágenes (numpy arrays BGR).
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Fichero no encontrado: {path}")

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return ImageLib._load_pdf(path)
        elif suffix in (".tiff", ".tif"):
            return ImageLib._load_tiff(path)
        else:
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError(f"No se pudo leer la imagen: {path}")
            return [img]

    @staticmethod
    def save(
        image: np.ndarray,
        path: str | Path,
        *,
        quality: int = 95,
        compression: str = "lzw",
        png_level: int = 6,
        dpi: int | None = None,
    ) -> Path:
        """Guarda imagen. Formato inferido por extensión.

        Usa Pillow internamente para soporte de DPI y compresión.

        Args:
            image: Imagen numpy (BGR o gris).
            path: Ruta de salida (extensión determina formato).
            quality: Calidad JPEG (1-100).
            compression: Compresión TIFF (none, lzw, zip, group4).
            png_level: Nivel de compresión PNG (0-9).
            dpi: Resolución en DPI (se escribe en metadatos).

        Returns:
            La ruta del fichero guardado.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        pil_img = ImageLib._ndarray_to_pil(image)
        suffix = path.suffix.lower()

        save_kwargs: dict = {}
        if dpi:
            save_kwargs["dpi"] = (dpi, dpi)

        if suffix in (".jpg", ".jpeg"):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
            # JPEG no soporta alpha
            if pil_img.mode == "RGBA":
                pil_img = pil_img.convert("RGB")
            elif pil_img.mode == "LA":
                pil_img = pil_img.convert("L")
            pil_img.save(str(path), "JPEG", **save_kwargs)

        elif suffix in (".tiff", ".tif"):
            tiff_comp = _TIFF_COMPRESSION.get(compression)
            if tiff_comp:
                save_kwargs["compression"] = tiff_comp
            pil_img.save(str(path), "TIFF", **save_kwargs)

        elif suffix == ".png":
            save_kwargs["compress_level"] = png_level
            pil_img.save(str(path), "PNG", **save_kwargs)

        elif suffix == ".bmp":
            pil_img.save(str(path), "BMP", **save_kwargs)

        else:
            # Fallback: dejar que Pillow adivine
            pil_img.save(str(path), **save_kwargs)

        return path

    # ------------------------------------------------------------------
    # Conversión de formato
    # ------------------------------------------------------------------

    @staticmethod
    def convert(
        image: np.ndarray,
        target_format: str,
        output_path: str | Path,
        **save_kwargs,
    ) -> Path:
        """Convierte una imagen a otro formato.

        Args:
            image: Imagen numpy (BGR).
            target_format: Extensión destino (sin punto): 'jpg', 'png', etc.
            output_path: Ruta de salida.
            **save_kwargs: Argumentos adicionales para save().

        Returns:
            La ruta del fichero guardado.
        """
        output_path = Path(output_path)
        # Asegurar extensión correcta
        expected_ext = f".{target_format.lower().strip('.')}"
        if output_path.suffix.lower() != expected_ext:
            output_path = output_path.with_suffix(expected_ext)
        return ImageLib.save(image, output_path, **save_kwargs)

    # ------------------------------------------------------------------
    # Merge / Split
    # ------------------------------------------------------------------

    @staticmethod
    def merge_to_pdf(
        images: list[np.ndarray | str | Path],
        output_path: str | Path,
        *,
        dpi: int = 200,
        quality: int = 85,
        append: bool = False,
    ) -> Path:
        """Combina imágenes en un PDF.

        Args:
            images: Lista de imágenes (ndarray) o rutas.
            output_path: Ruta del PDF de salida.
            dpi: Resolución para calcular tamaño de página.
            quality: Calidad JPEG dentro del PDF.
            append: Si True y el fichero ya existe, añade páginas al final.

        Returns:
            La ruta del PDF generado.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if append and output_path.exists():
            doc = pymupdf.open(str(output_path))
        else:
            doc = pymupdf.open()
        try:
            for item in images:
                img = ImageLib._resolve_image(item)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = img_rgb.shape[:2]

                page_w = w * 72.0 / dpi
                page_h = h * 72.0 / dpi

                pdf_page = doc.new_page(width=page_w, height=page_h)

                encode_params = [
                    cv2.IMWRITE_JPEG_QUALITY, quality,
                ]
                img_bytes = cv2.imencode(
                    ".jpg", img, encode_params,
                )[1].tobytes()
                pdf_page.insert_image(
                    pymupdf.Rect(0, 0, page_w, page_h),
                    stream=img_bytes,
                )

            doc.save(str(output_path))
            total_pages = doc.page_count
        finally:
            doc.close()

        log.info("PDF generado: %s (%d páginas)", output_path, total_pages)
        return output_path

    @staticmethod
    def merge_to_tiff(
        images: list[np.ndarray | str | Path],
        output_path: str | Path,
        *,
        compression: str = "lzw",
        dpi: int | None = None,
    ) -> Path:
        """Combina imágenes en un TIFF multipágina.

        Args:
            images: Lista de imágenes (ndarray) o rutas.
            output_path: Ruta del TIFF de salida.
            compression: Compresión TIFF (none, lzw, zip, group4).
            dpi: Resolución en DPI.

        Returns:
            La ruta del TIFF generado.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pil_images: list[Image.Image] = []
        for item in images:
            img = ImageLib._resolve_image(item)
            pil_images.append(ImageLib._ndarray_to_pil(img))

        if not pil_images:
            raise ValueError("No hay imágenes para combinar")

        save_kwargs: dict = {}
        tiff_comp = _TIFF_COMPRESSION.get(compression)
        if tiff_comp:
            save_kwargs["compression"] = tiff_comp
        if dpi:
            save_kwargs["dpi"] = (dpi, dpi)

        first = pil_images[0]
        rest = pil_images[1:] if len(pil_images) > 1 else []
        first.save(
            str(output_path), "TIFF",
            save_all=True,
            append_images=rest,
            **save_kwargs,
        )

        log.info("TIFF generado: %s (%d páginas)", output_path, len(images))
        return output_path

    @staticmethod
    def split(
        path: str | Path,
        output_dir: str | Path,
        *,
        format: str = "png",
        dpi: int = 300,
    ) -> list[Path]:
        """Separa un PDF o TIFF multipágina en imágenes individuales.

        Args:
            path: Ruta al fichero PDF o TIFF.
            output_dir: Directorio de salida.
            format: Formato de las imágenes de salida.
            dpi: DPI para renderizar PDF.

        Returns:
            Lista de rutas de las imágenes generadas.
        """
        path = Path(path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = ImageLib.load(path)
        ext = f".{format.lower().strip('.')}"
        result: list[Path] = []

        for i, img in enumerate(pages):
            out_path = output_dir / f"page_{i:04d}{ext}"
            ImageLib.save(img, out_path, dpi=dpi)
            result.append(out_path)

        log.info("Split %s: %d páginas → %s", path.name, len(result), output_dir)
        return result

    # ------------------------------------------------------------------
    # Resolución / DPI
    # ------------------------------------------------------------------

    @staticmethod
    def get_dpi(path: str | Path) -> tuple[float, float]:
        """Obtiene los DPI de un fichero de imagen.

        Args:
            path: Ruta al fichero.

        Returns:
            Tupla (dpi_x, dpi_y). Devuelve (72.0, 72.0) si no hay info.
        """
        try:
            with Image.open(str(path)) as img:
                info = img.info.get("dpi", (72.0, 72.0))
                return (float(info[0]), float(info[1]))
        except Exception:
            return (72.0, 72.0)

    @staticmethod
    def resize_to_dpi(
        image: np.ndarray,
        source_dpi: int,
        target_dpi: int,
    ) -> np.ndarray:
        """Redimensiona una imagen cambiando su resolución.

        Args:
            image: Imagen numpy.
            source_dpi: DPI original.
            target_dpi: DPI destino.

        Returns:
            Imagen redimensionada.
        """
        if source_dpi <= 0 or target_dpi <= 0:
            return image
        # DPI fuente inverosímil: asumir 300 (valor estándar de escáner)
        if source_dpi < 10:
            source_dpi = 300
        if source_dpi == target_dpi:
            return image

        scale = target_dpi / source_dpi
        h, w = image.shape[:2]
        new_w = int(w * scale)
        new_h = int(h * scale)

        interpolation = (
            cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
        )
        return cv2.resize(image, (new_w, new_h), interpolation=interpolation)

    # ------------------------------------------------------------------
    # Modo de color
    # ------------------------------------------------------------------

    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """Convierte a escala de grises.

        Args:
            image: Imagen numpy (BGR o ya gris).

        Returns:
            Imagen en escala de grises (1 canal).
        """
        if len(image.shape) == 2:
            return image
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def to_color(image: np.ndarray) -> np.ndarray:
        """Convierte a color (BGR 3 canales).

        Args:
            image: Imagen numpy.

        Returns:
            Imagen en color (3 canales BGR).
        """
        if len(image.shape) == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image

    @staticmethod
    def to_bw(image: np.ndarray, threshold: int = 128) -> np.ndarray:
        """Convierte a blanco y negro (umbralización).

        Args:
            image: Imagen numpy.
            threshold: Umbral (0-255).

        Returns:
            Imagen binaria (1 canal, 0 o 255).
        """
        gray = ImageLib.to_grayscale(image)
        _, bw = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        return bw

    @staticmethod
    def get_color_mode(image: np.ndarray) -> str:
        """Detecta el modo de color de una imagen.

        Returns:
            'color', 'grayscale' o 'bw'.
        """
        if len(image.shape) == 2:
            # Verificar si es binaria (solo 0 y 255)
            unique = np.unique(image)
            if len(unique) <= 2 and all(v in (0, 255) for v in unique):
                return "bw"
            return "grayscale"

        if image.shape[2] >= 3:
            # Verificar si todos los canales son iguales (gris en formato BGR)
            b, g, r = image[:, :, 0], image[:, :, 1], image[:, :, 2]
            if np.array_equal(b, g) and np.array_equal(g, r):
                unique = np.unique(b)
                if len(unique) <= 2 and all(v in (0, 255) for v in unique):
                    return "bw"
                return "grayscale"
            return "color"

        return "grayscale"

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _ndarray_to_pil(image: np.ndarray) -> Image.Image:
        """Convierte ndarray BGR a PIL Image RGB."""
        if len(image.shape) == 2:
            return Image.fromarray(image, mode="L")
        if image.shape[2] == 4:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
            return Image.fromarray(rgb, mode="RGBA")
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb, mode="RGB")

    @staticmethod
    def _load_pdf(path: Path, dpi: int = 300) -> list[np.ndarray]:
        """Extrae cada página de un PDF como imagen."""
        images: list[np.ndarray] = []
        doc = pymupdf.open(str(path))
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=dpi)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n,
                )
                if pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                elif pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
                images.append(img.copy())
        finally:
            doc.close()
        return images

    @staticmethod
    def _load_tiff(path: Path) -> list[np.ndarray]:
        """Carga TIFF (soporta multipágina)."""
        success, frames = cv2.imreadmulti(str(path))
        if success and frames:
            return list(frames)
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is not None:
            return [img]
        raise ValueError(f"No se pudo leer el TIFF: {path}")

    @staticmethod
    def _resolve_image(item: np.ndarray | str | Path) -> np.ndarray:
        """Resuelve un item a ndarray: carga si es ruta."""
        if isinstance(item, np.ndarray):
            return item
        imgs = ImageLib.load(item)
        if not imgs:
            raise ValueError(f"No se pudo cargar: {item}")
        return imgs[0]
