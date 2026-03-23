"""Configuración de formato de imagen para aplicaciones."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ImageConfig:
    """Configuración de formato de imagen (escaneo).

    Define cómo se almacenan las imágenes capturadas por el escáner.
    Los archivos importados se almacenan en su formato original.
    """

    format: str = "tiff"              # tiff, png, jpg, pdf
    color_mode: str = "color"         # color, grayscale, bw
    jpeg_quality: int = 85            # 1-100
    tiff_compression: str = "lzw"     # none, lzw, zip, group4
    png_compression: int = 6          # 0-9
    bw_threshold: int = 128           # 0-255


def parse_image_config(json_str: str) -> ImageConfig:
    """Parsea la configuración de imagen desde JSON.

    Args:
        json_str: Cadena JSON con la configuración.

    Returns:
        ImageConfig con los valores deserializados.
    """
    if not json_str or json_str == "{}":
        return ImageConfig()
    data = json.loads(json_str)
    return ImageConfig(**{
        k: v for k, v in data.items()
        if k in ImageConfig.__dataclass_fields__
    })


def serialize_image_config(config: ImageConfig) -> str:
    """Serializa la configuración de imagen a JSON.

    Args:
        config: Configuración a serializar.

    Returns:
        Cadena JSON.
    """
    from dataclasses import asdict
    return json.dumps(asdict(config))
