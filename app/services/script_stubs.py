"""Generador de stubs inline para scripts de usuario.

Produce un bloque de código Python con declaraciones de tipo para que
IDEs externos (Pylance, Pyright) ofrezcan autocompletado y no muestren
warnings. El bloque se inyecta al inicio de archivos temporales y se
elimina automáticamente al guardar.
"""

from __future__ import annotations

STUB_DELIMITER = "# === DOCSCAN STUBS (no editar) ==="

_IMPORTS = """\
from __future__ import annotations
import logging
import re
import json
import datetime
from pathlib import Path
from typing import Any
"""

_TYPE_DEFS = """\
class BarcodeResult:
    \"\"\"Código de barras detectado por un BarcodeStep.\"\"\"
    value: str              # Contenido decodificado
    symbology: str          # Tipo: CODE128, QR_CODE, EAN13, etc.
    engine: str             # Motor que lo detectó: "pyzbar" o "zxing"
    step_id: str            # ID del BarcodeStep que lo encontró
    quality: float          # Calidad de lectura (0.0 - 1.0)
    pos_x: int              # Posición X del bounding box (píxeles)
    pos_y: int              # Posición Y del bounding box
    pos_w: int              # Ancho del bounding box
    pos_h: int              # Alto del bounding box
    role: str               # Rol asignado por script ("separator", "content", etc.)

class PageFlags:
    \"\"\"Flags mutables de la página durante el procesamiento.\"\"\"
    needs_review: bool          # True si la página requiere revisión manual
    review_reason: str          # Motivo de la revisión
    script_errors: list[dict[str, Any]]   # Errores de scripts (no detienen el pipeline)
    processing_errors: list[str]          # Errores de procesamiento general

class AppContext:
    \"\"\"Configuración de la aplicación activa (solo lectura).\"\"\"
    id: int
    name: str                                   # Nombre de la aplicación
    description: str
    config: dict[str, Any]                      # Config de AI (provider, model, etc.)
    batch_fields_def: list[dict[str, Any]]      # Definición de campos de lote
    transfer_config: dict[str, Any]             # Config de transferencia (modo, destino)
    auto_transfer: bool                         # Transferir automáticamente al cerrar lote
    output_format: str                          # Formato de salida: "tiff", "pdf", "jpeg"

class BatchContext:
    \"\"\"Lote activo (lectura y escritura en .fields).\"\"\"
    id: int
    fields: dict[str, Any]      # Valores de los campos del lote (editable)
    state: str                  # Estado: "created", "open", "ready_to_export", "exported"
    page_count: int             # Número de páginas en el lote
    folder_path: str            # Ruta de la carpeta del lote en disco
    hostname: str               # Nombre del equipo que creó el lote

class PageContext:
    \"\"\"Página actual del pipeline (lectura y escritura).\"\"\"
    page_index: int                     # Índice de la página en el lote (base 0)
    image: Any                          # numpy.ndarray (BGR) o None
    barcodes: list[BarcodeResult]       # Barcodes acumulados por BarcodeSteps
    ocr_text: str                       # Texto OCR extraído
    ai_fields: dict[str, Any]           # Campos extraídos por AI
    flags: PageFlags                    # Flags de revisión y errores
    fields: dict[str, Any]              # Campos de indexación (editable)

class PipelineContext:
    \"\"\"Control de flujo del pipeline (solo disponible en ScriptStep).\"\"\"
    def skip_step(self) -> None: ...                            # Salta el paso actual
    def skip_to(self, step_id: str) -> None: ...                # Salta hasta el paso con este ID
    def abort(self, reason: str) -> None: ...                   # Aborta el pipeline completo
    def repeat_step(self) -> None: ...                          # Repite el paso actual (máx 3 veces)
    def replace_image(self, image: Any) -> None: ...            # Reemplaza la imagen de la página
    def get_metadata(self, key: str) -> Any: ...                # Lee metadato del pipeline
    def set_metadata(self, key: str, value: Any) -> None: ...   # Escribe metadato del pipeline
"""

_VARS_PIPELINE = """\
# --- Variables disponibles en ScriptStep ---
log: logging.Logger         # Logger para mensajes (log.info, log.warning, etc.)
http: Any                   # Cliente HTTP (httpx.Client) o None si no configurado
app: AppContext             # Aplicación activa (solo lectura)
batch: BatchContext         # Lote activo
page: PageContext           # Página actual del pipeline
pipeline: PipelineContext   # Control de flujo del pipeline
"""

_VARS_EVENT_BASE = """\
# --- Variables disponibles en este evento ---
log: logging.Logger         # Logger para mensajes (log.info, log.warning, etc.)
http: Any                   # Cliente HTTP (httpx.Client) o None si no configurado
app: AppContext             # Aplicación activa (solo lectura)
batch: BatchContext         # Lote activo
"""

_VARS_EVENT_PAGE = """\
page: PageContext           # Página actual
"""

# Eventos que reciben page como argumento
_EVENTS_WITH_PAGE = {
    "on_scan_complete",
    "on_transfer_page",
    "on_key_event",
}


def generate_stubs(context_type: str, event_name: str = "") -> str:
    """Genera bloque de stubs para inyectar en archivo temporal.

    Args:
        context_type: "pipeline" para ScriptStep, "event" para eventos.
        event_name: Nombre del evento (solo si context_type="event").

    Returns:
        Bloque de código Python con tipos, delimitado por marcadores.
    """
    parts = [STUB_DELIMITER, _IMPORTS, _TYPE_DEFS]

    if context_type == "pipeline":
        parts.append(_VARS_PIPELINE)
    else:
        parts.append(_VARS_EVENT_BASE)
        if event_name in _EVENTS_WITH_PAGE:
            parts.append(_VARS_EVENT_PAGE)

    parts.append(STUB_DELIMITER)
    parts.append("")

    return "\n".join(parts)


def strip_stubs(code: str) -> str:
    """Elimina el bloque de stubs de un código fuente."""
    lines = code.split("\n")
    result = []
    inside_stubs = False
    found_end = False

    for line in lines:
        if line.strip() == STUB_DELIMITER:
            if not inside_stubs:
                inside_stubs = True
                continue
            else:
                inside_stubs = False
                found_end = True
                continue
        if not inside_stubs:
            result.append(line)

    # Si no encontramos bloque completo, devolver el código original
    if inside_stubs and not found_end:
        return code

    # Eliminar líneas vacías al inicio resultantes de eliminar stubs
    while result and not result[0].strip():
        result.pop(0)

    return "\n".join(result)
