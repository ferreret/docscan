"""Dataclasses de todos los tipos de paso del pipeline.

Cada paso hereda de PipelineStep y define los campos específicos
de su tipo. El serializador usa el campo ``type`` como discriminador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StepType = Literal[
    "image_op",
    "barcode",
    "ocr",
    "ai",
    "script",
]


@dataclass
class PipelineStep:
    """Paso base del pipeline."""

    id: str
    type: StepType
    enabled: bool = True


@dataclass
class ImageOpStep(PipelineStep):
    """Operación de transformación de imagen.

    Operaciones disponibles: AutoDeskew, ConvertTo1Bpp, Crop,
    CropWhiteBorders, CropBlackBorders, Resize, Rotate, RotateAngle,
    SetBrightness, SetContrast, RemoveLines, FxDespeckle, FxGrayscale,
    FxNegative, FxDilate, FxErode, FxEqualizeIntensity, FloodFill,
    RemoveHolePunch, SetResolution, SwapColor, KeepChannel, RemoveChannel,
    ScaleChannel.
    """

    type: Literal["image_op"] = "image_op"
    op: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    window: tuple[int, int, int, int] | None = None  # (x, y, w, h) px


@dataclass
class BarcodeStep(PipelineStep):
    """Lectura de códigos de barras.

    Acumula resultados en ``page.barcodes`` sin semántica de rol.
    La distinción separador/contenido la decide un ScriptStep posterior.
    """

    type: Literal["barcode"] = "barcode"
    engine: Literal["motor1", "motor2"] = "motor1"
    symbologies: list[str] = field(default_factory=list)  # [] = todas
    regex: str = ""  # "" = sin filtro
    regex_include_symbology: bool = False
    orientations: list[str] = field(
        default_factory=lambda: ["horizontal", "vertical"]
    )
    quality_threshold: float = 0.0
    window: tuple[int, int, int, int] | None = None  # None = página completa


@dataclass
class OcrStep(PipelineStep):
    """Reconocimiento óptico de caracteres."""

    type: Literal["ocr"] = "ocr"
    engine: Literal["rapidocr", "easyocr", "tesseract"] = "rapidocr"
    languages: list[str] = field(default_factory=lambda: ["es"])
    full_page: bool = True
    window: tuple[int, int, int, int] | None = None


@dataclass
class AiStep(PipelineStep):
    """Extracción de campos o clasificación por IA."""

    type: Literal["ai"] = "ai"
    provider: Literal["anthropic", "openai", "local_ocr"] = "anthropic"
    template_id: int | None = None
    fallback_provider: str | None = None


@dataclass
class ScriptStep(PipelineStep):
    """Código Python con acceso al contexto completo y control del pipeline."""

    type: Literal["script"] = "script"
    label: str = ""
    entry_point: str = ""
    script: str = ""


# Mapa tipo -> clase para deserialización
STEP_TYPE_MAP: dict[str, type[PipelineStep]] = {
    "image_op": ImageOpStep,
    "barcode": BarcodeStep,
    "ocr": OcrStep,
    "ai": AiStep,
    "script": ScriptStep,
}
