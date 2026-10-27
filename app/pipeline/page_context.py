"""Contextos ligeros para el pipeline (duck-type compatible).

Dataclasses que PipelineExecutor manipula durante la ejecución.
Separadas de los workers Qt para permitir reutilización en web y CLI.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


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

    @classmethod
    def from_application(cls, app: Any) -> AppContext:
        """Construye el contexto completo desde una aplicación de BD.

        Un JSON de configuración corrupto deja ese atributo vacío en vez de
        impedir que corran los scripts.

        Args:
            app: Registro ``Application`` (o cualquier objeto con sus campos).

        Returns:
            El AppContext con todos los atributos rellenos.
        """
        return cls(
            id=app.id or 0,
            name=app.name or "",
            description=app.description or "",
            config=_load_json(app.ai_config_json, {}, "ai_config_json"),
            batch_fields_def=_load_json(app.batch_fields_json, [], "batch_fields_json"),
            transfer_config=_load_json(app.transfer_json, {}, "transfer_json"),
            pipeline_steps=_load_json(app.pipeline_json, [], "pipeline_json"),
            auto_transfer=bool(app.auto_transfer),
            output_format=app.output_format or "tiff",
        )


def _load_json(raw: str | None, default: Any, column: str) -> Any:
    """Decodifica una columna JSON; devuelve ``default`` si falta o no vale."""
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except TypeError, ValueError:
        log.warning("JSON inválido en %s; se usa vacío en el AppContext", column)
        return default
    return value if isinstance(value, type(default)) else default
