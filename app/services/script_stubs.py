"""Generador de stubs inline para scripts de usuario.

Produce un bloque de comentarios con las clases/funciones disponibles
según el contexto (ScriptStep o evento de ciclo de vida). El bloque se
inyecta al inicio de archivos temporales para que IDEs externos ofrezcan
autocompletado.
"""

from __future__ import annotations

STUB_DELIMITER = "# === DOCSCAN STUBS (no editar) ==="

_COMMON_BUILTINS = """\
# Builtins disponibles:
#   log       — logging.Logger
#   http      — httpx.Client | None
#   re        — módulo re
#   json      — módulo json
#   datetime  — módulo datetime
#   Path      — pathlib.Path"""

_APP_CONTEXT = """\
# app: AppContext
#   .id: int
#   .name: str
#   .description: str
#   .config: dict[str, Any]          — AI config
#   .batch_fields_def: list[dict]    — definición de campos de lote
#   .transfer_config: dict[str, Any] — config de transferencia
#   .auto_transfer: bool
#   .output_format: str"""

_BATCH_CONTEXT = """\
# batch: BatchContext
#   .id: int
#   .fields: dict[str, Any]          — campos del lote (valores)
#   .state: str                      — estado actual
#   .page_count: int
#   .folder_path: str
#   .hostname: str"""

_PAGE_CONTEXT = """\
# page: PageContext
#   .page_index: int
#   .image: numpy.ndarray | None
#   .barcodes: list[BarcodeResult]   — .value, .symbology, .engine, .role, ...
#   .ocr_text: str
#   .ai_fields: dict[str, Any]
#   .flags: PageFlags                — .needs_review, .review_reason, .script_errors
#   .fields: dict[str, Any]          — campos de indexación"""

_PIPELINE_CONTEXT = """\
# pipeline: PipelineContext
#   .skip_step()                     — salta el paso actual
#   .skip_to(step_id)                — salta hasta un paso
#   .abort(reason)                   — aborta el pipeline
#   .repeat_step()                   — repite el paso actual
#   .replace_image(image)            — reemplaza imagen de la página
#   .get_metadata(key) / .set_metadata(key, value)"""

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
        Bloque de comentarios delimitado.
    """
    lines = [STUB_DELIMITER, "#"]

    if context_type == "pipeline":
        lines.append("# Contexto: ScriptStep del pipeline")
        lines.append("#")
        lines.append(_APP_CONTEXT)
        lines.append(_BATCH_CONTEXT)
        lines.append(_PAGE_CONTEXT)
        lines.append(_PIPELINE_CONTEXT)
    else:
        lines.append(f"# Contexto: evento '{event_name}'")
        lines.append("#")
        lines.append(_APP_CONTEXT)
        lines.append(_BATCH_CONTEXT)
        if event_name in _EVENTS_WITH_PAGE:
            lines.append(_PAGE_CONTEXT)

    lines.append("#")
    lines.append(_COMMON_BUILTINS)
    lines.append("#")
    lines.append(STUB_DELIMITER)
    lines.append("")

    return "\n".join(lines)


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
