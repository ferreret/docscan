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
- page.is_separator — bool, the page opens a new logical document (read/write)
- page.separator_value — str, value that identifies that document (read/write)
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
- pipeline.set_metadata(key: str, value: Any) — store metadata (lives for the CURRENT PAGE only)
- pipeline.get_metadata(key: str) -> Any — retrieve metadata. A new PipelineContext is created
  for every page, so metadata can NOT carry values from one page to the next.
- pipeline.get_step_result(step_id: str) -> Any — result from a previous step

### Built-in variables
- log — Python logger (use log.info(), log.warning(), etc.)
- http — httpx client for HTTP requests
- re — regex module
- json — json module
- datetime — datetime module
- Path — pathlib.Path

### Common script patterns

**Document separators:** prefer the declarative condition of the BarcodeStep
(`separator_enabled`, `separator_by`, `separator_regex`…). A script only for
conditions it cannot express; a script after the BarcodeStep has the last word:
```python
def process(app, batch, page, pipeline):
    seps = [bc for bc in page.barcodes if bc.value.startswith("SEP-")]
    page.is_separator = bool(seps)
    page.separator_value = seps[0].value[4:] if seps else ""
```
A document is the run of pages from one separator page to the next (pages
before the first separator form an implicit document). Never mark barcodes
with a role to separate documents: the separator belongs to the PAGE.

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
    "on_app_start": 'def on_app_start(app, batch):\n    """Runs when the application opens in the Workbench."""',
    "on_app_end": 'def on_app_end(app, batch):\n    """Runs when the application closes."""',
    "on_import": 'def on_import(app, batch):\n    """Runs when the operator starts an import. Return any non-None value to replace the standard import; return None to keep it."""',
    "on_scan_complete": 'def on_scan_complete(app, batch):\n    """Runs ONCE after the pipeline finishes for ALL pages in the batch. Receives no pages."""',
    "on_transfer_validate": (
        "def on_transfer_validate(app, batch, pages, documents) -> bool:\n"
        '    """Runs before transfer, after the required batch fields are checked.\n'
        "    `pages` and `documents` are optional parameters (declare only what you use).\n"
        "    pages: .page_index, .fields, .barcodes (.value, .symbology), .is_separator,\n"
        "    .separator_value. documents: .index, .separator_value, .pages, .fields.\n"
        '    Return False to cancel. An exception also cancels it and its message reaches the operator."""'
    ),
    "on_transfer_advanced": (
        "def on_transfer_advanced(app, batch, pages, result):\n"
        '    """Runs AFTER the simple transfer (if enabled), in the Workbench and in the\n'
        "    unattended worker alike. `pages`: list with .image_path, .page_index, .fields,\n"
        "    .ocr_text, .first_barcode, .barcodes (.value, .symbology), .is_separator,\n"
        "    .separator_value, .image (loaded on demand). Optional `documents` (logical\n"
        "    documents: .index, .separator_value, .pages). `result`: TransferResult of the\n"
        "    simple transfer. There is NO batch.pages.\n"
        '    Return False or raise to make the transfer fail: the batch is NOT marked as exported."""'
    ),
    "on_transfer_page": 'def on_transfer_page(app, batch, page_index, success):\n    """Runs after each page is copied by the simple transfer (Workbench only)."""',
    "on_navigate_prev": 'def on_navigate_prev(app, batch, current_page_index, total_pages):\n    """Custom previous navigation. Return the page index to go to (int), or None."""',
    "on_navigate_next": 'def on_navigate_next(app, batch, current_page_index, total_pages):\n    """Custom next navigation. Return the page index to go to (int), or None."""',
    "on_navigate_script": (
        "def on_navigate_script(app, batch, current_page_index, total_pages, pages):\n"
        '    """Custom viewer navigation button. `pages` is a list of dicts with page_index,\n'
        '    barcodes (value, symbology, role) and needs_review. Return the target page index (int)."""'
    ),
    "on_key_event": 'def on_key_event(app, batch, key):\n    """Custom key event handler. \'key\' is a string with the key name."""',
    "on_batch_loaded": 'def on_batch_loaded(app, batch):\n    """Runs when a batch is opened in the Workbench (after the pipeline has finished)."""',
    "on_page_changed": 'def on_page_changed(app, batch, page, page_index):\n    """Runs each time the active page changes. \'page\' has id, page_index, fields, barcodes, ocr_text."""',
    "init_global": 'def init_global():\n    """Runs at program startup (launcher-level global script). Receives NO arguments."""',
    "verification_panel": (
        "class MyVerificationPanel(VerificationPanel):\n"
        '    """Custom verification panel plugin.\n'
        "    Available methods to override: setup_ui(), on_page_changed(page_index),\n"
        "    on_pipeline_completed(page_index), on_batch_loaded(),\n"
        "    validate_page(page_index) -> (bool, str), validate() -> (bool, str), cleanup().\n"
        "    Available via self.api: get_page_image(), get_page_barcodes(), get_page_ocr_text(),\n"
        "    get_page_fields(), set_page_field(name, value), get_batch_fields(),\n"
        '    set_batch_field(name, value), navigate_to(index), log(msg)."""'
    ),
}
