"""Servicio AI MODE — asistente IA unificado para gestion de aplicaciones.

Puede crear, modificar, duplicar, listar y eliminar aplicaciones
completas de DocScan Studio a partir de instrucciones en lenguaje natural.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.pipeline.serializer import deserialize, serialize
from app.services._assistant_constants import (
    EVENT_SIGNATURES,
    IMAGE_OPS_REFERENCE,
    SCRIPT_API_REFERENCE,
)

log = logging.getLogger(__name__)

_API_TIMEOUT = 90
_RATE_LIMIT_RETRIES = 1
_RATE_LIMIT_DELAY = 2.0
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_OPENAI_MODEL = "gpt-4o"
_MAX_TOKENS = 8192

# ---------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------

_PIPELINE_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["image_op", "barcode", "ocr", "script"]},
        "enabled": {"type": "boolean", "default": True},
        "op": {"type": "string"},
        "params": {"type": "object"},
        "window": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
        "engine": {"type": "string"},
        "symbologies": {"type": "array", "items": {"type": "string"}},
        "regex": {"type": "string"},
        "regex_include_symbology": {"type": "boolean"},
        "orientations": {"type": "array", "items": {"type": "string"}},
        "quality_threshold": {"type": "number"},
        "languages": {"type": "array", "items": {"type": "string"}},
        "full_page": {"type": "boolean"},
        "label": {"type": "string"},
        "entry_point": {"type": "string"},
        "script": {"type": "string"},
    },
    "required": ["type"],
}

_BATCH_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "type": {"type": "string", "enum": ["texto", "fecha", "lista", "numerico"]},
        "config": {"type": "object"},
        "required": {"type": "boolean", "default": False},
    },
    "required": ["label", "type"],
}

_APP_CONFIG_PROPERTIES = {
    "name": {"type": "string"},
    "description": {"type": "string"},
    "active": {"type": "boolean", "default": True},
    "pipeline": {"type": "array", "items": _PIPELINE_STEP_SCHEMA},
    "events": {
        "type": "object",
        "description": "Map of event_name -> Python code string.",
        "additionalProperties": {"type": "string"},
    },
    "batch_fields": {"type": "array", "items": _BATCH_FIELD_SCHEMA},
    "index_fields": {"type": "array", "items": _BATCH_FIELD_SCHEMA},
    "image_config": {
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["tiff", "jpeg", "png"]},
            "color_mode": {"type": "string", "enum": ["color", "grayscale", "bw"]},
            "jpeg_quality": {"type": "integer", "minimum": 1, "maximum": 100},
            "tiff_compression": {"type": "string"},
            "png_compression": {"type": "integer"},
            "bw_threshold": {"type": "integer"},
        },
    },
    "general": {
        "type": "object",
        "properties": {
            "auto_transfer": {"type": "boolean"},
            "close_after_transfer": {"type": "boolean"},
            "output_format": {"type": "string"},
            "default_tab": {"type": "string"},
            "scanner_backend": {"type": "string"},
            "background_color": {"type": "string"},
        },
    },
    "ai_config": {
        "type": "object",
        "properties": {
            "barcode_regex": {"type": "string"},
            "barcode_fixed_value": {"type": "string"},
        },
    },
    "transfer": {
        "type": "object",
        "description": "Transfer configuration.",
        "properties": {
            "standard_enabled": {"type": "boolean", "default": True},
            "mode": {"type": "string", "enum": ["folder", "pdf", "pdfa", "csv"]},
            "destination": {"type": "string"},
            "filename_pattern": {"type": "string"},
            "create_subdirs": {"type": "boolean", "default": True},
            "include_metadata": {"type": "boolean", "default": False},
            "output_format": {"type": "string", "enum": ["", "tiff", "png", "jpg", "pdf"]},
            "output_dpi": {"type": "integer"},
            "output_color_mode": {"type": "string", "enum": ["", "color", "grayscale", "bw"]},
            "output_jpeg_quality": {"type": "integer", "minimum": 1, "maximum": 100},
            "output_tiff_compression": {"type": "string", "enum": ["lzw", "zip", "none", "group4"]},
            "output_png_compression": {"type": "integer", "minimum": 0, "maximum": 9},
            "output_bw_threshold": {"type": "integer", "minimum": 0, "maximum": 255},
            "pdf_dpi": {"type": "integer", "minimum": 72, "maximum": 600},
            "pdf_jpeg_quality": {"type": "integer", "minimum": 1, "maximum": 100},
            "csv_separator": {"type": "string"},
            "csv_fields": {"type": "array", "items": {"type": "string"}},
        },
    },
    "explanation": {"type": "string"},
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_applications",
        "description": "Refresh and return the current list of all applications with their summary.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_application",
        "description": "Get the full configuration of a specific application by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name."},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "create_application",
        "description": (
            "Create a new application with full or partial configuration. "
            "Include pipeline steps with working Python code for ScriptSteps. "
            "Include event code for lifecycle events."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_APP_CONFIG_PROPERTIES,
            },
            "required": ["name", "explanation"],
        },
    },
    {
        "name": "update_application",
        "description": (
            "Update specific fields of an existing application. "
            "Only include fields that need to change — absent fields are left unchanged."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Name of the app to update."},
                **_APP_CONFIG_PROPERTIES,
            },
            "required": ["app_name", "explanation"],
        },
    },
    {
        "name": "duplicate_application",
        "description": (
            "Clone an existing application with a new name, optionally applying modifications."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_app_name": {"type": "string"},
                "new_name": {"type": "string"},
                **{k: v for k, v in _APP_CONFIG_PROPERTIES.items() if k != "name"},
            },
            "required": ["source_app_name", "new_name", "explanation"],
        },
    },
    {
        "name": "delete_application",
        "description": "Delete an application and all its batches. This is irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["app_name", "explanation"],
        },
    },
    {
        "name": "set_event_code",
        "description": (
            "Set Python code for a specific lifecycle event of a specific application. "
            "Generate complete, working Python code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "event_name": {"type": "string"},
                "code": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["app_name", "event_name", "code", "explanation"],
        },
    },
]

_OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]

# ---------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------

@dataclass
class AiModeToolCall:
    """Una llamada a tool del modelo."""
    tool_name: str
    tool_input: dict[str, Any]
    explanation: str = ""


@dataclass
class AiModeResponse:
    """Respuesta del asistente AI MODE."""
    tool_calls: list[AiModeToolCall] = field(default_factory=list)
    text: str = ""
    error: str | None = None


# ---------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are the AI MODE assistant for DocScan Studio, a document scanning and processing application.

You have FULL CONTROL over all applications. You can:
- List all applications and their configurations
- Create new applications from scratch with complete configuration
- Modify any aspect of any existing application
- Duplicate applications with modifications
- Delete applications
- Generate Python code for pipeline scripts and lifecycle events

IMPORTANT RULES:
- You can call MULTIPLE tools in a single response when needed.
- For pipeline steps, always include ALL steps (not just changes) in the pipeline array.
- Respond in the same language as the user's message.
- Do NOT call list_applications or get_application unless the user explicitly asks — you already have a summary below.
- **MINIMIZE ScriptSteps**: Only add a ScriptStep when the built-in steps (image_op, barcode, ocr) and transfer config CANNOT achieve the goal. The BarcodeStep `regex` field can filter barcodes by pattern without a script. The transfer config `filename_pattern` can rename files using barcode values without a script. Only use ScriptStep for complex custom logic.
- **auto_transfer defaults to false**. Only set it to true if the user explicitly asks for automatic transfer.
- When the user asks for file export with renaming, custom paths, etc., prefer configuring the `transfer` object with `filename_pattern` FIRST. Only use `on_transfer_advanced` event for logic that cannot be expressed with the transfer config.

---

{image_ops_reference}

## BarcodeStep fields
- engine: 'motor1' (pyzbar+opencv) or 'motor2' (zxing-cpp)
- symbologies: list of barcode types (e.g., ['Code128', 'QR', 'EAN13', 'Code39', 'DataMatrix', 'PDF417']). Empty list = detect all types.
- regex: optional regex filter on barcode value — only barcodes matching this pattern are kept. Example: "^[A-Z]\\d{{8}}$" for letter + 8 digits. This avoids needing a ScriptStep for simple filtering.
- regex_include_symbology: if true, the symbology prefix is included when checking the regex
- orientations: ['horizontal', 'vertical', 'diagonal']
- quality_threshold: 0.0-1.0 confidence threshold
- window: [x, y, w, h] in pixels or null for full page

## OcrStep fields
- engine: 'rapidocr' (fast, recommended), 'easyocr' (needs GPU), 'tesseract' (fallback)
- languages: ISO codes, e.g., ['es', 'en', 'fr', 'de', 'ca']
- full_page: true for entire page, false for window region only
- window: [x, y, w, h] or null

{script_api_reference}

## Lifecycle events
Events are Python scripts that run at specific lifecycle moments.
Each event has a specific function signature:
{event_signatures}

---

## Manual barcode config (in "ai_config" object)
Configures the manual barcode entry button in the Workbench toolbar.
- barcode_regex (str): Regex pattern to validate manual barcode input. Example: "^[A-Z]\\d{{8}}$" for letter + 8 digits. If set, the user MUST enter a value matching this pattern. Uses `re.fullmatch()`.
- barcode_fixed_value (str): If set, clicking the manual barcode button inserts this value directly without prompting the user. Useful for separator pages or fixed markers.

**IMPORTANT**: When the user asks for manual barcode entry with a specific format, ALWAYS set `barcode_regex` in `ai_config`. This is the SAME regex pattern used in BarcodeStep.regex — they should match so that manual entry follows the same validation as automatic detection.

Example: If BarcodeStep uses regex "^[A-Z]\\d{{8}}$", set ai_config.barcode_regex to the same pattern.

## General settings (in "general" object)
- auto_transfer (bool, default FALSE): Automatically start transfer after pipeline completes. Usually false.
- close_after_transfer (bool, default false): Close workbench after successful transfer.
- output_format (str, default "tiff"): Default image format for the workbench.
- default_tab (str, default "lote"): Default tab shown when workbench opens ("lote" or "log").
- scanner_backend (str): "sane" (Linux), "twain" (Windows), "wia" (Windows). Empty = auto-detect by platform.
- background_color (str): Hex color for workbench background (e.g., "#1e1e2e").

## Batch field types (in "batch_fields" array)
Dynamic form fields shown to the user when creating a batch:
- texto: simple text field (no config needed)
- fecha: date field, config: {{"format": "dd/MM/yyyy" | "yyyy-MM-dd" | "dd-MM-yyyy"}}
- lista: dropdown list, config: {{"values": ["Option1", "Option2", ...]}}
- numerico: numeric field, config: {{"min": 0, "max": 100, "step": 1}}

## Index fields (in "index_fields" array)
Field definitions for per-page indexed data (auto-populated by pipeline ScriptSteps via `page.fields`).
Same structure as batch_fields: each has label, type, config, required.
Unlike batch_fields (user-entered at batch creation), index_fields are filled automatically by pipeline scripts.
Example: a ScriptStep sets `page.fields["doc_type"] = "invoice"` and an index_field with label "doc_type" defines how it's displayed.

## Image config (scanner storage format)
How scanned images are stored internally (before transfer):
- format: "tiff" (default), "jpeg", "png"
- color_mode: "color" (default), "grayscale", "bw"
- jpeg_quality: 1-100 (default 85)
- tiff_compression: "none", "lzw", "zip", "group4" (default "lzw")
- png_compression: 0-9 (default 6)
- bw_threshold: 0-255 (default 128) for B/W conversion

## Transfer config (in "transfer" object)
Controls how pages are exported. Two mechanisms: standard transfer (config-based) or advanced transfer (script-based event).

### Standard transfer (config-based, NO scripting needed):
- standard_enabled (bool, default true): Enable standard transfer. If false, only on_transfer_advanced runs.
- mode: "folder" (copy files), "pdf" (single PDF), "pdfa" (PDF/A archival), "csv" (export metadata)
- destination: path string, e.g., "/media/user/export/"
- filename_pattern: template for file names. Variables:
  - {{batch_id}} — batch number
  - {{page_index}} — page number (use :04d for zero-padding)
  - {{first_barcode}} — value of the first barcode detected on the page
  - {{campo_nombre}} — any batch field value (spaces replaced by underscores)
  - Example: "{{first_barcode}}" → renames files to barcode value
  - Example: "{{batch_id}}/{{page_index:04d}}" → creates subdirectory per batch
- create_subdirs (bool, default true): Create batch_ID subdirectories
- include_metadata (bool, default false): Write .json metadata files alongside images
- output_format: "" (keep original), "tiff", "png", "jpg" — format conversion on export
- output_dpi: 0 (keep original) or target DPI
- output_color_mode: "" (keep), "grayscale", "bw" — color reduction on export
- output_jpeg_quality: 1-100 (default 85)
- output_tiff_compression: "lzw", "zip", "none", "group4"
- output_png_compression: 0-9 (default 6)
- output_bw_threshold: 0-255 (default 128) — threshold for B/W conversion on export

### PDF options (when mode is "pdf" or "pdfa"):
- pdf_dpi: 72-600 (default 200)
- pdf_jpeg_quality: 1-100 (default 85)

### CSV options (when mode is "csv"):
- csv_separator: default ";"
- csv_fields: list of field names to export

### Advanced transfer (script-based, for complex logic):
Use the `on_transfer_advanced` event ONLY when standard transfer cannot achieve the goal.
Set `standard_enabled: false` in transfer config when using only advanced transfer.

#### Available utilities in transfer scripts:
- `ImageLib` — import with `from app.services.image_lib import ImageLib`
  - `ImageLib.merge_to_pdf(images, output_path, dpi=200, quality=85, append=False)` — Create or APPEND to a PDF. When `append=True` and the file exists, new pages are added to the existing PDF.
  - `ImageLib.merge_to_tiff(images, output_path, compression="lzw", dpi=None)` — Create multi-page TIFF. To append to existing TIFF: load existing pages with `ImageLib.load(path)` first, then merge all together.
  - `ImageLib.load(path)` — Load image(s), returns `list[np.ndarray]`. Works with multi-page TIFF/PDF.

#### Example 1: Export with date subfolders and barcode filenames (simple copy):
```python
def on_transfer_advanced(app, batch, result):
    import shutil
    from datetime import date
    dest_base = Path("/path/to/export")
    date_folder = dest_base / date.today().strftime("%Y%m%d")
    date_folder.mkdir(parents=True, exist_ok=True)
    for page in batch.pages:
        if page.barcodes:
            barcode_val = page.barcodes[0].value
            ext = Path(page.image_path).suffix
            dest = date_folder / f"{{barcode_val}}{{ext}}"
            shutil.copy2(page.image_path, dest)
    result["exported_count"] = len(batch.pages)
```

#### Example 2: Append to existing file when duplicate (merge pages into multi-page TIFF):
When the destination file already exists, APPEND the new page to it instead of overwriting or adding a counter.
```python
def on_transfer_advanced(app, batch, result):
    from app.services.image_lib import ImageLib
    from datetime import date
    dest_base = Path("/path/to/export")
    date_folder = dest_base / date.today().strftime("%Y%m%d")
    date_folder.mkdir(parents=True, exist_ok=True)
    for page in batch.pages:
        if page.barcodes:
            barcode_val = page.barcodes[0].value
            dest = date_folder / f"{{barcode_val}}.tiff"
            if dest.exists():
                # Append: load existing pages + new page, merge all
                existing = ImageLib.load(str(dest))
                new_page = ImageLib.load(page.image_path)
                ImageLib.merge_to_tiff(existing + new_page, str(dest))
            else:
                import shutil
                shutil.copy2(page.image_path, dest)
    result["exported_count"] = len(batch.pages)
```

#### Example 3: Append to existing PDF:
```python
def on_transfer_advanced(app, batch, result):
    from app.services.image_lib import ImageLib
    from datetime import date
    dest_base = Path("/path/to/export")
    date_folder = dest_base / date.today().strftime("%Y%m%d")
    date_folder.mkdir(parents=True, exist_ok=True)
    for page in batch.pages:
        if page.barcodes:
            barcode_val = page.barcodes[0].value
            dest = date_folder / f"{{barcode_val}}.pdf"
            # merge_to_pdf with append=True adds pages if file exists
            ImageLib.merge_to_pdf(
                [page.image_path], str(dest), append=True,
            )
    result["exported_count"] = len(batch.pages)
```

**IMPORTANT: When the user asks for "merge", "append", or "attach" when a file already exists, use `ImageLib.merge_to_tiff()` or `ImageLib.merge_to_pdf(append=True)`. Do NOT use a numeric counter suffix — that creates separate files instead of merging.**

## IMPORTANT: ScriptStep vs Events vs Config
- **Built-in pipeline steps** (image_op, barcode, ocr): Use these FIRST. They cover deskew, rotation, brightness, barcode detection with regex filtering, OCR, etc.
- **ScriptStep**: ONLY for complex per-page logic that built-in steps cannot handle (e.g., conditional field assignment based on multiple barcode values, complex business rules).
- **Transfer config**: Use `filename_pattern` with `{{first_barcode}}` to rename files by barcode. Use `mode`, `destination`, format options. NO script needed for most transfers.
- **on_transfer_advanced event**: For transfer logic that cannot be expressed with transfer config (e.g., conditional file routing, API calls, custom folder structures, **merging pages into existing files**).
- **on_transfer_validate event**: Pre-transfer validation. Return False to cancel.
- **ai_config**: ALWAYS set `barcode_regex` when the user mentions manual barcode entry with a specific format. Match it to the BarcodeStep regex if both are configured.

## Current applications
{apps_summary}
"""


_EVENT_SIGS_TEXT = "\n".join(
    f"- **{name}**:\n```python\n{sig}\n```"
    for name, sig in EVENT_SIGNATURES.items()
)

_SYSTEM_PROMPT_STATIC = _SYSTEM_PROMPT_TEMPLATE.format(
    image_ops_reference=IMAGE_OPS_REFERENCE,
    script_api_reference=SCRIPT_API_REFERENCE,
    event_signatures=_EVENT_SIGS_TEXT,
    apps_summary="{apps_summary}",
)


def _build_system_prompt(apps_summary: str) -> str:
    """Construye el system prompt insertando solo la parte dinamica."""
    return _SYSTEM_PROMPT_STATIC.replace("{apps_summary}", apps_summary, 1)


# ---------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------

class AiModeAssistantService:
    """Asistente AI MODE para gestion completa de aplicaciones.

    Args:
        provider: "anthropic" o "openai".
        api_key: Clave API.
        model: Modelo (None = default por proveedor).
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        if provider not in ("anthropic", "openai"):
            raise ValueError(f"Proveedor no soportado: {provider}")
        self._provider = provider
        self._api_key = api_key
        self._model = model or (
            _DEFAULT_ANTHROPIC_MODEL if provider == "anthropic"
            else _DEFAULT_OPENAI_MODEL
        )
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self._provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self._api_key, timeout=_API_TIMEOUT,
            )
        else:
            import openai
            self._client = openai.OpenAI(
                api_key=self._api_key, timeout=_API_TIMEOUT,
            )
        return self._client

    def generate(
        self,
        messages: list[dict[str, str]],
        apps_summary: str,
    ) -> AiModeResponse:
        """Genera respuesta a partir de mensajes y contexto de apps.

        Args:
            messages: Historial [{role, content}, ...].
            apps_summary: JSON con resumen de apps actuales.

        Returns:
            AiModeResponse con tool_calls, text, o error.
        """
        system_prompt = _build_system_prompt(apps_summary)
        try:
            if self._provider == "anthropic":
                return self._call_anthropic(system_prompt, messages)
            else:
                return self._call_openai(system_prompt, messages)
        except Exception as e:
            error_msg = _classify_error(e)
            log.error("Error API %s: %s", self._provider, e)
            return AiModeResponse(error=error_msg)

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _call_anthropic(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> AiModeResponse:
        client = self._get_client()
        response = _call_with_retry(
            lambda: client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            )
        )

        tool_calls: list[AiModeToolCall] = []
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "tool_use":
                tc = AiModeToolCall(
                    tool_name=block.name,
                    tool_input=_process_tool_input(block.name, block.input),
                    explanation=block.input.get("explanation", ""),
                )
                tool_calls.append(tc)
            elif block.type == "text":
                text_parts.append(block.text)

        return AiModeResponse(
            tool_calls=tool_calls,
            text="\n".join(text_parts),
        )

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _call_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> AiModeResponse:
        client = self._get_client()

        openai_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        response = _call_with_retry(
            lambda: client.chat.completions.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                messages=openai_messages,
                tools=_OPENAI_TOOLS,
            )
        )

        choice = response.choices[0] if response.choices else None
        if choice is None:
            return AiModeResponse(error="Respuesta vacia del modelo.")

        msg = choice.message
        text = msg.content or ""

        if not msg.tool_calls:
            return AiModeResponse(text=text)

        tool_calls: list[AiModeToolCall] = []
        for tc in msg.tool_calls:
            try:
                tool_input = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                return AiModeResponse(
                    text=text,
                    error="El asistente genero argumentos JSON invalidos.",
                )
            tool_calls.append(AiModeToolCall(
                tool_name=tc.function.name,
                tool_input=_process_tool_input(tc.function.name, tool_input),
                explanation=tool_input.get("explanation", ""),
            ))

        return AiModeResponse(tool_calls=tool_calls, text=text)


# ---------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------

def _process_tool_input(tool_name: str, tool_input: dict) -> dict:
    """Procesa el input de un tool call: asigna IDs, valida pipeline."""
    if tool_name in ("create_application", "update_application", "duplicate_application"):
        pipeline = tool_input.get("pipeline")
        if pipeline:
            for step_data in pipeline:
                if "id" not in step_data or not step_data.get("id"):
                    step_data["id"] = f"step_{uuid.uuid4().hex[:8]}"
    return tool_input


def validate_pipeline(steps_data: list[dict]) -> str | None:
    """Valida un pipeline deserializandolo. Retorna error o None."""
    try:
        steps_json = json.dumps(steps_data, ensure_ascii=False)
        deserialize(steps_json)
        return None
    except Exception as e:
        return str(e)


def _call_with_retry(fn: Any, retries: int = _RATE_LIMIT_RETRIES) -> Any:
    for attempt in range(1 + retries):
        try:
            return fn()
        except Exception as e:
            error_type = type(e).__name__
            is_rate_limit = "rate" in error_type.lower() or "429" in str(e)
            if is_rate_limit and attempt < retries:
                log.warning("Rate limit, reintentando en %.1fs...", _RATE_LIMIT_DELAY)
                time.sleep(_RATE_LIMIT_DELAY)
                continue
            raise


def _classify_error(e: Exception) -> str:
    error_str = str(e).lower()
    error_type = type(e).__name__.lower()
    if "401" in error_str or "unauthorized" in error_str:
        return "API key invalida. Revisa tu configuracion."
    if "429" in error_str or "rate" in error_type:
        return "Limite de peticiones alcanzado. Intentalo en unos segundos."
    if "timeout" in error_str or "timeout" in error_type:
        return "Timeout en la peticion. Intentalo de nuevo."
    if "connection" in error_str or "network" in error_str:
        return "Error de conexion. Verifica tu conexion a internet."
    return f"Error del proveedor: {e}"
