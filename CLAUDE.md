# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

DocScan Studio is a PySide6 desktop application for batch document capture, processing, and indexing with generative AI support. Inspired by Flexibar.NET.

It is a **multi-application framework**, not a monolithic app:
- **Launcher** lists N "applications" (process profiles)
- Each **application** has fully independent config: pipeline, scripts, transfer, AI
- **Workbench** is the exploitation window that loads and runs a specific application

See `REQUIREMENTS.md` for full functional requirements and UI layout specs.

## Commands

```bash
# Environment setup (Python 3.14 required, invoke as python3.14 on Xubuntu)
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
python3.14 main.py                                    # Launcher
python3.14 main.py "App Name"                         # Direct app launch
python3.14 main.py --direct-mode "App Name"           # Headless mode
python3.14 -m docscan_worker --batch-path /path        # Unattended worker

# Tests
pytest tests/ -v --tb=short                            # All tests
pytest tests/test_foo.py -v                            # Single file
pytest tests/test_foo.py::TestClass::test_method -v    # Single test

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Lint
ruff check app/
ruff format app/
```

## Stack

- **Python 3.14** | **PySide6** | **SQLAlchemy 2.x** + **SQLite WAL mode**
- **Barcode**: `pyzbar`+`opencv-python` (Motor 1), `zxing-cpp` (Motor 2)
- **Image pipeline**: `opencv-python` + `Pillow`
- **OCR**: `rapidocr-onnxruntime` (primary), `easyocr` (alternative, needs PyTorch), `pytesseract` (fallback)
- **AI**: `anthropic` SDK, `openai` SDK
- **PDF**: `pymupdf` (fitz) -- input/output including PDF/A
- **HTTP**: `httpx` | **Config**: `pydantic-settings` | **Encryption**: `cryptography` (Fernet)
- **Scanner Linux**: `python-sane` (SANE) | **Scanner Windows**: `pytwain` (TWAIN), `pywin32` (WIA)
- **Automation**: `watchdog`, `APScheduler` | **Testing**: `pytest`, `pytest-qt`

## Architecture

### Pipeline -- the central processing model

Each page is processed through a **dynamic, composable pipeline**: an ordered list of steps defined per application. Step types: `image_op`, `barcode`, `ocr`, `script`, `condition`, `http_request`.

Key files:
- `app/pipeline/steps.py` -- dataclasses for all step types (PipelineStep, ImageOpStep, BarcodeStep, OcrStep, ScriptStep, ConditionStep, HttpRequestStep)
- `app/pipeline/context.py` -- PipelineContext with flow control (skip_step, skip_to, abort, repeat_step, replace_image, get/set_metadata)
- `app/pipeline/executor.py` -- PipelineExecutor (stateless between pages, one instance per app)
- `app/pipeline/serializer.py` -- JSON <-> list[PipelineStep] (serialize/deserialize)

Pipeline JSON is stored in `pipeline_json` column of `applications` table.

### Application lifecycle entry points (separate from pipeline)

Defined in Events tab, executed outside the pipeline: `on_app_start`, `on_app_end`, `on_import`, `on_scan_complete`, `on_transfer_validate`, `on_transfer_advanced`, `on_transfer_page`, `on_navigate_prev/next`, `on_key_event`, `init_global`.

### Script context

All scripts (ScriptStep + lifecycle events) receive: `app` (AppContext), `batch` (BatchContext), `page` (PageContext with `.barcodes`, `.ocr_text`, `.fields`, `.flags`), `pipeline` (PipelineContext -- only in ScriptStep). Built-in: `log`, `http` (httpx), `re`, `json`, `datetime`, `Path`.

### Key services

- `app/services/script_engine.py` -- compiles scripts once at app load (cached by step.id), catches all exceptions
- `app/services/barcode_service.py` -- Motor 1 (pyzbar) + Motor 2 (zxing-cpp)
- `app/services/image_pipeline.py` -- all ImageOp implementations
- `app/services/scanner_service.py` -- BaseScanner ABC with SaneScanner (Linux) + TwainScanner + WiaScanner (Windows). Auto-selects by platform.
- `app/providers/` -- BaseProvider ABC with anthropic/openai/local_ocr implementations (Strategy pattern)
- `app/workers/` -- QThread workers (scan, recognition, transfer)

### Database

SQLite with **mandatory WAL mode** for UI + DocScanWorker concurrency. Repository pattern (one per entity, receives Session by parameter).

## Conventions

- Classes: `PascalCase` | functions/variables: `snake_case` | constants: `UPPER_SNAKE_CASE`
- UI labels in Spanish | docstrings in Spanish, Google style
- Type hints required on public functions
- Use `logging` stdlib, never `print()`
- Paths with `pathlib.Path` and `platformdirs`, never hardcoded
- Styles in `.qss` files under `resources/styles/`

## Critical rules

- **Never block the UI thread**: all heavy work in QThread, communicate via Signal
- **SQLite WAL mode is mandatory**: set on every engine connect event
- **Sessions always in context manager**: never global Session objects
- **API keys encrypted with Fernet** in `~/.docscan/secrets.enc`, never in plaintext
- **ScriptStep errors don't stop the pipeline**: log to `page.flags.script_errors`
- **Scripts compile once at app load** (cached by step.id), not per page execution
- **repeat_step has a max limit** (default 3, configurable): executor enforces it with PipelineAbortError
- **BarcodeStep is role-agnostic**: accumulates in `page.barcodes` without separator/content semantics. Roles are assigned by a subsequent ScriptStep
- **No business logic in PySide6 widgets**: keep it in services/pipeline
- **Don't reference barcodes as standalone context object**: always `page.barcodes`

## Implementation order

1. `app/pipeline/steps.py` (all step dataclasses including `condition` and `http_request`)
2. `app/pipeline/context.py` (PipelineContext + repeat_step limit)
3. `app/pipeline/serializer.py`
4. `config/settings.py` + `config/secrets.py`
5. `app/db/database.py` (WAL mode + repositories)
6. `app/models/`
7. `app/services/script_engine.py`
8. `app/services/image_pipeline.py`
9. `app/services/barcode_service.py`
10. `app/providers/` + `app/services/ocr_service.py`
11. `app/pipeline/executor.py`
12. `app/services/scanner_service.py`
13. `app/services/import_service.py`
14. `app/services/batch_service.py` + `app/services/transfer_service.py`
15. `app/services/notification_service.py`
16. `app/ui/launcher/`
17. `app/ui/configurator/tabs/tab_pipeline.py` + step dialogs
18. `app/ui/configurator/tabs/tab_events.py`
19. `app/ui/workbench/`
20. `app/ui/batch_manager/`
21. `docscan_worker/worker_main.py` + `docscan_worker/folder_watcher.py`
22. `tests/`

## Tool usage rules

Always use context7 when generating code that uses any library from the stack
(PySide6, SQLAlchemy, opencv, pyzbar, zxing-cpp, pymupdf, anthropic, openai,
httpx, watchdog, APScheduler). Resolve the library id and fetch docs without
waiting for me to ask explicitly.
