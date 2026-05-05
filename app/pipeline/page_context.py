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
