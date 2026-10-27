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

    Por defecto la operación solo afecta a la imagen que circula por el
    pipeline (preproceso para leer barcodes u OCR): el fichero archivado
    y transferido conserva el original del escaneo. Con ``persist=True``
    el resultado sustituye al fichero de la página, que es lo que se
    espera de operaciones como AutoDeskew, CropWhiteBorders o Rotate.
    """

    type: Literal["image_op"] = "image_op"
    op: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    window: tuple[int, int, int, int] | None = None  # (x, y, w, h) px
    persist: bool = False  # ¿El resultado sustituye al fichero de la página?


@dataclass
class BarcodeStep(PipelineStep):
    """Lectura de códigos de barras.

    Acumula resultados en ``page.barcodes`` sin semántica de rol: los
    barcodes no se marcan nunca como separador o contenido.

    Puede declarar una condición de separador de documento (campos
    ``separator_*``, mismas claves que FlexibarNET10). Si está activa, la
    condición marca la **página** (``page.is_separator`` y
    ``page.separator_value``) y es autoritativa: al reprocesar pisa la marca
    manual. Un ScriptStep posterior puede sobrescribirla.
    """

    type: Literal["barcode"] = "barcode"
    engine: Literal["motor1", "motor2"] = "motor1"
    symbologies: list[str] = field(default_factory=list)  # [] = todas
    regex: str = ""  # "" = sin filtro
    regex_include_symbology: bool = False
    orientations: list[str] = field(default_factory=lambda: ["horizontal", "vertical"])
    quality_threshold: float = 0.0
    window: tuple[int, int, int, int] | None = None  # None = página completa

    # Separador de documento (paridad FlexibarNET10)
    separator_enabled: bool = False
    separator_by: Literal["symbology", "regex", "fixed_value"] = "regex"
    separator_symbology: str = ""
    separator_regex: str = ""
    separator_fixed_value: str = ""
    # Evalúa la regex sobre "NN"+valor (NN = número legacy de la simbología)
    separator_regex_include_symbology: bool = False
    # Valida lo que teclea el operador al marcar a mano (no la detección)
    separator_manual_regex: str = ""
    # Valor con el que se pre-rellena la marca manual si la página no tiene código
    separator_default_value: str = ""


@dataclass
class OcrStep(PipelineStep):
    """Reconocimiento óptico de caracteres."""

    type: Literal["ocr"] = "ocr"
    engine: Literal["rapidocr", "easyocr", "tesseract"] = "rapidocr"
    languages: list[str] = field(default_factory=lambda: ["es"])
    full_page: bool = True
    window: tuple[int, int, int, int] | None = None


@dataclass
class ScriptStep(PipelineStep):
    """Código Python con acceso al contexto completo y control del pipeline."""

    type: Literal["script"] = "script"
    label: str = ""
    entry_point: str = ""
    script: str = ""


# Tipos eliminados: el serializer los salta con warning por compatibilidad
REMOVED_STEP_TYPES: frozenset[str] = frozenset({"ai"})

# Mapa tipo -> clase para deserialización
STEP_TYPE_MAP: dict[str, type[PipelineStep]] = {
    "image_op": ImageOpStep,
    "barcode": BarcodeStep,
    "ocr": OcrStep,
    "script": ScriptStep,
}
