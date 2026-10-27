"""Contextos ligeros para el pipeline (duck-type compatible).

Dataclasses que PipelineExecutor manipula durante la ejecución.
Separadas de los workers Qt para permitir reutilización en web y CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PageFlags:
    """Flags mutables de una página durante el pipeline."""

    needs_review: bool = False
    review_reason: str = ""
    script_errors: list[dict[str, Any]] = field(default_factory=list)
    processing_errors: list[str] = field(default_factory=list)


@dataclass
class BarcodeResult:
    """Resultado de barcode detectado por el pipeline."""

    value: str = ""
    symbology: str = ""
    engine: str = ""
    step_id: str = ""
    quality: float = 0.0
    pos_x: int = 0
    pos_y: int = 0
    pos_w: int = 0
    pos_h: int = 0
    role: str = ""


@dataclass
class PageContext:
    """Contexto de página que el PipelineExecutor manipula.

    Compatible duck-type con los accesos que hace el executor:
    ``page.image``, ``page.barcodes``, ``page.ocr_text``,
    ``page.flags``.
    """

    page_index: int
    id: int = 0
    image: np.ndarray | None = None
    image_replaced: bool = False
    barcodes: list[BarcodeResult] = field(default_factory=list)
    ocr_text: str = ""
    ocr_regions: list[Any] = field(default_factory=list)
    flags: PageFlags = field(default_factory=PageFlags)
    fields: dict[str, Any] = field(default_factory=dict)
    # Separador de documento. Se inicializan con lo que hay en BD; si el
    # pipeline los cambia (detección de un BarcodeStep o un script),
    # ``separator_decided`` pasa a True y el llamador los persiste.
    is_separator: bool = False
    separator_value: str = ""
    separator_decided: bool = field(default=False, repr=False)

    def __setattr__(self, name: str, value: Any) -> None:
        # Durante __init__ ``separator_decided`` aún no existe: solo cuentan
        # las asignaciones posteriores.
        if name in ("is_separator", "separator_value") and (
            "separator_decided" in self.__dict__
        ):
            object.__setattr__(self, "separator_decided", True)
        object.__setattr__(self, name, value)


# Longitud máxima del valor de separador guardado (como FlexibarNET10).
MAX_SEPARATOR_VALUE_LENGTH = 500


def separator_state(page: Any) -> dict[str, Any]:
    """Estado de separador de una página de BD, para inicializar su contexto.

    Sin él, una página marcada a mano perdería la marca al reprocesarla
    con un pipeline que no tiene detección.
    """
    return {
        "is_separator": bool(getattr(page, "is_separator", False)),
        "separator_value": getattr(page, "separator_value", "") or "",
    }


def persist_separator(page_ctx: Any, page_db: Any) -> None:
    """Guarda en la página de BD la marca de separador si el pipeline la tocó."""
    if not getattr(page_ctx, "separator_decided", False):
        return
    page_db.is_separator = bool(page_ctx.is_separator)
    page_db.separator_value = (page_ctx.separator_value or "")[
        :MAX_SEPARATOR_VALUE_LENGTH
    ]


@dataclass
class BatchContext:
    """Contexto ligero de lote para scripts."""

    id: int = 0
    fields: dict[str, Any] = field(default_factory=dict)
    state: str = "created"
    page_count: int = 0
    folder_path: str = ""
    hostname: str = ""


@dataclass
class AppContext:
    """Contexto ligero de aplicación para scripts."""

    id: int = 0
    name: str = ""
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    batch_fields_def: list[dict[str, Any]] = field(default_factory=list)
    transfer_config: dict[str, Any] = field(default_factory=dict)
    pipeline_steps: list[dict[str, Any]] = field(default_factory=list)
    auto_transfer: bool = False
    output_format: str = "tiff"
