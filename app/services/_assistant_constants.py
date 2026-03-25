"""Constantes compartidas para los asistentes IA.

Usadas por pipeline_assistant.py y ai_mode_assistant.py.
"""

from __future__ import annotations

# ---------------------------------------------------------------
# Referencia de operaciones de imagen
# ---------------------------------------------------------------

IMAGE_OPS_REFERENCE = """\
## Available image operations (ImageOpStep.op)

Each operation accepts specific params as a dict:

| Operation | Description | Params |
|-----------|-------------|--------|
| AutoDeskew | Auto-straighten skewed scans | max_angle: float (default 15.0) |
| ConvertTo1Bpp | Convert to black & white (1-bit) | threshold: int (0-255, default 128) |
| Crop | Crop to a fixed rectangle | x, y, w, h: int (pixels) |
| CropWhiteBorders | Remove white margins | tolerance: int (0-255, default 10) |
| CropBlackBorders | Remove black margins | tolerance: int (0-255, default 10) |
| Resize | Resize image | width: int, height: int (pixels; 0 = auto-aspect) |
| Rotate | Rotate 90/180/270 degrees | angle: int (90, 180, or 270) |
| RotateAngle | Rotate arbitrary angle | angle: float (degrees) |
| SetBrightness | Adjust brightness | value: int (-100 to 100) |
| SetContrast | Adjust contrast | value: float (0.5 to 3.0; 1.0 = no change) |
| RemoveLines | Remove horizontal/vertical lines | direction: str ("H", "V", or "HV") |
| FxDespeckle | Remove noise/speckles | kernel_size: int (3, 5, 7; default 3) |
| FxGrayscale | Convert to grayscale | (no params) |
| FxNegative | Invert image colors | (no params) |
| FxDilate | Morphological dilation | kernel_size: int (default 3), iterations: int (default 1) |
| FxErode | Morphological erosion | kernel_size: int (default 3), iterations: int (default 1) |
| FxEqualizeIntensity | Histogram equalization | (no params) |
| FloodFill | Flood fill from a point | x: int, y: int, color: list[int] (BGR), tolerance: int |
| RemoveHolePunch | Remove hole punch marks | (no params) |
| SetResolution | Set image DPI metadata | dpi: int |
| SwapColor | Replace one color with another | from_color: list[int], to_color: list[int], tolerance: int |
| KeepChannel | Keep only one color channel | channel: str ("R", "G", or "B") |
| RemoveChannel | Remove one color channel | channel: str ("R", "G", or "B") |
| ScaleChannel | Scale intensity of one channel | channel: str, factor: float |
"""

# ---------------------------------------------------------------
# Referencia de API de scripting
# ---------------------------------------------------------------

SCRIPT_API_REFERENCE = """\
## Script context API

Scripts (ScriptStep and lifecycle events) receive these objects:

### page (PageContext)
- page.image — np.ndarray (BGR), the current page image
- page.barcodes — list of barcode results, each with:
    .value (str), .symbology (str), .rect (tuple x,y,w,h or None)
- page.ocr_text — str, full OCR text of the page
- page.ocr_regions — list of OcrRegion with word-level bounding boxes
- page.fields — dict[str, str], key-value fields for indexing
- page.flags:
    .needs_review (bool), .review_reason (str),
    .script_errors (list[dict]), .processing_errors (list[str])

### batch (BatchContext)
- batch.id — int
- batch.name — str
- batch.path — Path to batch directory
- batch.fields — dict[str, str], batch-level fields

### app (AppContext)
- app.name — str, application name
- app.config — dict, application configuration

### pipeline (PipelineContext) — ONLY available in ScriptStep, NOT in events
- pipeline.skip_step(step_id: str) — skip a specific step
- pipeline.skip_to(step_id: str) — skip all steps until step_id
- pipeline.abort(reason: str) — abort pipeline, mark page for review
- pipeline.repeat_step(step_id: str) — re-execute a step (max 3 repeats)
- pipeline.replace_image(img: np.ndarray) — replace current image
- pipeline.set_metadata(key: str, value: Any) — store metadata
- pipeline.get_metadata(key: str) -> Any — retrieve metadata
- pipeline.get_step_result(step_id: str) -> Any — result from a previous step

### Built-in variables
- log — Python logger (use log.info(), log.warning(), etc.)
- http — httpx client for HTTP requests
- re — regex module
- json — json module
- datetime — datetime module
- Path — pathlib.Path

### Common script patterns

**Classify barcodes as separator/content:**
```python
def process(app, batch, page, pipeline):
    for bc in page.barcodes:
        if bc.value.startswith("SEP"):
            page.fields["separator"] = bc.value
        else:
            page.fields["content_barcode"] = bc.value
```

**Conditional skip:**
```python
def process(app, batch, page, pipeline):
    if not page.barcodes:
        pipeline.skip_step("ocr_step_id")
```

**HTTP call:**
```python
def process(app, batch, page, pipeline):
    resp = http.post("https://api.example.com/index",
                     json={"doc_id": page.fields.get("id", "")})
    if resp.status_code == 200:
        page.fields["indexed"] = "true"
```

**Abort on condition:**
```python
def process(app, batch, page, pipeline):
    if not page.ocr_text.strip():
        pipeline.abort("Blank page detected")
```
"""

# ---------------------------------------------------------------
# Firmas de eventos lifecycle
# ---------------------------------------------------------------

EVENT_SIGNATURES: dict[str, str] = {
    "on_app_start": "def on_app_start(app, batch):\n    \"\"\"Runs when the application opens in the Workbench.\"\"\"",
    "on_app_end": "def on_app_end(app, batch):\n    \"\"\"Runs when the application closes.\"\"\"",
    "on_import": "def on_import(app, batch):\n    \"\"\"Replaces standard import logic when defined. Called on 'Process' button with file/PDF source.\"\"\"",
    "on_scan_complete": "def on_scan_complete(app, batch):\n    \"\"\"Runs ONCE after the pipeline finishes for ALL pages in the batch.\"\"\"",
    "on_transfer_validate": "def on_transfer_validate(app, batch) -> bool:\n    \"\"\"Runs before transfer. Return False to cancel transfer.\"\"\"",
    "on_transfer_advanced": "def on_transfer_advanced(app, batch, result):\n    \"\"\"Replaces simple transfer when defined. Full batch access for custom transfer logic.\"\"\"",
    "on_transfer_page": "def on_transfer_page(app, batch, page, result):\n    \"\"\"Runs after copying each page during simple transfer.\"\"\"",
    "on_navigate_prev": "def on_navigate_prev(app, batch):\n    \"\"\"Custom previous navigation handler.\"\"\"",
    "on_navigate_next": "def on_navigate_next(app, batch):\n    \"\"\"Custom next navigation handler.\"\"\"",
    "on_navigate_script": "def on_navigate_script(app, batch):\n    \"\"\"Custom viewer navigation button handler.\"\"\"",
    "on_key_event": "def on_key_event(app, batch, key):\n    \"\"\"Custom key event handler. 'key' is a string with the key name.\"\"\"",
    "init_global": "def init_global(app, batch):\n    \"\"\"Runs at program startup (launcher-level global script).\"\"\"",
    "verification_panel": (
        "class MyVerificationPanel(VerificationPanel):\n"
        "    \"\"\"Custom verification panel plugin.\n"
        "    Available methods to override: setup_ui(), on_page_changed(page_index),\n"
        "    on_pipeline_completed(page_index), on_batch_loaded(),\n"
        "    validate_page(page_index) -> (bool, str), validate() -> (bool, str), cleanup().\n"
        "    Available via self.api: get_page_image(), get_page_barcodes(), get_page_ocr_text(),\n"
        "    get_page_fields(), set_page_field(name, value), get_batch_fields(),\n"
        "    set_batch_field(name, value), navigate_to(index), log(msg).\"\"\""
    ),
}
