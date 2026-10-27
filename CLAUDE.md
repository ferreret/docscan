# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session context — read this first

`.claude/memory/` holds the accumulated project context from previous sessions,
versioned so every machine starts from the same history. **Read
`.claude/memory/MEMORY.md` at the start of a session**: it is the index, and it
links to the individual entries (current focus, known bugs, closed decisions,
working preferences).

Native Claude Code memory lives outside the repo and does not travel between
machines. When you write or change memory during a session, mirror it back with
`cp ~/.claude/projects/<slug>/memory/*.md .claude/memory/` before committing.
The repo is public — check the diff for credentials first. See
`.claude/memory/README.md`.

## Project overview

DocScan Studio is a PySide6 desktop application for batch document capture, processing, and indexing with generative AI support. Inspired by Flexibar.NET.

It is a **multi-application framework**, not a monolithic app:
- **Launcher** lists N "applications" (process profiles)
- Each **application** has fully independent config: pipeline, scripts, transfer, AI
- **Workbench** is the exploitation window that loads and runs a specific application

See `REQUIREMENTS.md` for full functional requirements and UI layout specs.

## Commands

Python 3.14 is required. Always run through the project venv (`.venv/bin/python`
or an activated `.venv`), never a bare `python3.14`: on the current Linux machine
(minis-nick-linux, Ubuntu 26.04) there is no system Python 3.14, the interpreter
comes from **uv**.

```bash
# Environment setup (uv-managed Python 3.14)
uv venv --python 3.14 --managed-python
uv pip install -r requirements-dev.txt     # runtime + test/lint tooling
# System packages (Ubuntu): libzbar0t64 (pyzbar), libsane-dev (python-sane),
# libxcb-cursor0 (Qt xcb), build-essential

# Run
.venv/bin/python main.py                                 # Launcher
.venv/bin/python main.py "App Name"                      # Direct app launch
.venv/bin/python main.py --direct-mode "App Name"        # Headless mode
.venv/bin/python -m docscan_worker --app-name "App Name" --watch /in   # Unattended worker
.venv/bin/python -m docscan_worker --app-name "App Name" --process-pending

# Tests (offscreen: no window, no display needed)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q          # All tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_foo.py  # Single file
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_foo.py::TestClass::test_method

# Database migrations (the app applies them itself at startup via run_migrations)
.venv/bin/alembic revision --autogenerate -m "description"

# UI screenshots for docs (docs/screenshots + docs-web) and the portfolio.
# Isolated (temp data/QSettings, offscreen, no network), neutral demo data.
.venv/bin/python tools/ui_snapshots.py [--theme light] [--only NAME ...] [--out DIR]
.venv/bin/python tools/ui_snapshots.py --portfolio ../portfolio/public/docscan-studio.webp

# Hospital Arnau archive apps (ported from FlexibarNET10) into a test DB, plus
# synthetic pages with real barcodes. Never seeds the user's DB by default.
.venv/bin/python tools/seed_apps_arnau.py --db /tmp/arnau.db --export-base /tmp/out --paginas /tmp/pages --escaner sane

# Linux/Wayland: icon in the dock when running from source (writes
# ~/.local/share/applications/docscan.desktop; --uninstall removes it)
.venv/bin/python tools/install_desktop_entry.py

# Lint
.venv/bin/ruff check .
.venv/bin/ruff format app/
```

Desktop only: the web SaaS part (`web/`, Docker, PostgreSQL, MinIO, Redis, API,
ARQ worker) is **archived and not set up on this machine**. Docker is not
installed. Do not propose setting it up; the web tests auto-skip without their
dependencies (`tests/conftest.py`).

### On Windows

The commands above assume Linux. On Windows the equivalents are:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\activate          # instead of source .venv/bin/activate
python main.py                  # i.e. .venv\Scripts\python.exe
```

`requirements.txt` already has platform markers: `pytwain`/`pywin32` install only
on Windows, `python-sane` only on Linux. The scanner backend is selected
automatically by `app/services/scanner_service.py`.

Repo tooling that is platform-sensitive:

- **Hooks** (`.claude/hooks/*.sh`) are bash and run under **Git Bash**, which
  Claude Code uses by default on Windows when it is installed. Without Git Bash
  they do not run: no automatic ruff formatting and, more importantly, no
  protection of `.env`/`secrets.enc`. `jq` is optional — the hooks fall back to
  `grep`/`sed` if it is missing, as Git Bash does not ship it.
- **`.mcp.json`** uses `${CLAUDE_PROJECT_DIR:-.}` so paths resolve per machine.
  The `sqlite` server defaults to the Linux DB path; on Windows set
  `DOCSCAN_DB_PATH` (typically `%LOCALAPPDATA%\docscan\docscan.db`).
- The `postgres` MCP server belongs to the archived web project and needs `.env`;
  it will simply fail to start without it, which is harmless.

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

Each page is processed through a **dynamic, composable pipeline**: an ordered list of steps defined per application. Step types: `image_op`, `barcode`, `ocr`, `script`.

Key files:
- `app/pipeline/steps.py` -- dataclasses for all step types (PipelineStep, ImageOpStep, BarcodeStep, OcrStep, ScriptStep)
- `app/pipeline/context.py` -- PipelineContext with flow control (skip_step, skip_to, abort, repeat_step, replace_image, get/set_metadata)
- `app/pipeline/executor.py` -- PipelineExecutor (stateless between pages, one instance per app)
- `app/pipeline/serializer.py` -- JSON <-> list[PipelineStep] (serialize/deserialize)
- `app/pipeline/separator.py` + `app/models/document.py` -- document separator condition and logical documents (`split_documents`): a document is the run of pages from one separator page to the next, computed on the fly, never stored

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
- `app/services/ai_mode_assistant.py` + `app/services/pipeline_assistant.py` -- AI assistants using the `anthropic` SDK directly (shared constants in `_assistant_constants.py`)
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
- **API keys encrypted with Fernet** in `secrets.enc` under the platformdirs config dir (`~/.config/docscan/` on Linux, `config/settings.py`), never in plaintext
- **ScriptStep errors don't stop the pipeline**: log to `page.flags.script_errors`
- **Scripts compile once at app load** (cached by source hash, not by step.id), not per page execution
- **A script failure is never treated as success** (FlexibarNET10 parity): it must surface in `script_errors`, the Log panel or as a failed transfer. Validation and advanced-transfer events run through `ScriptEngine.run_event_checked` in `app/services/transfer_flow.py`, shared by the Workbench and the unattended worker
- **Functional parity with FlexibarNET10**: when DocScan and Flexibar solve the same problem, follow Flexibar's documented behaviour (manual), same config keys and tokens. Deviations only by explicit decision
- **repeat_step has a max limit** (default 3, configurable): executor enforces it with PipelineAbortError
- **BarcodeStep does not assign roles to barcodes**: it accumulates in `page.barcodes` without separator/content semantics. It may declare a separator condition (`separator_*` fields, FlexibarNET10 parity) that marks the **page** (`page.is_separator` / `page.separator_value`), never the barcode. Scripts can override `page.is_separator`. See `docs/diseno_separadores_documento_2026-10-26.md`
- **No business logic in PySide6 widgets**: keep it in services/pipeline
- **Don't reference barcodes as standalone context object**: always `page.barcodes`

## Implementation order

The original 22-step build order (pipeline → config → DB → services → UI →
worker → tests) is **complete** (releases v0.1.0–v0.1.7). Current work is
prioritised in `docs/propuestas_desde_flexibarnet10_2026-10-26.md` (lote 3 done
in v0.1.7; lotes 4–5 pending; lote 6 slices S1–S2 done, status in §8 of
`docs/diseno_separadores_documento_2026-10-26.md`).

## Tool usage rules

When generating code that uses any library from the stack (PySide6, SQLAlchemy,
opencv, pyzbar, zxing-cpp, pymupdf, anthropic, openai, httpx, watchdog,
APScheduler), check its real API first without waiting for me to ask: use
context7 if it is configured in the session (it is not in `.mcp.json`), otherwise
read the installed package in `.venv` (the pinned version in `requirements.txt` is
the one that ships).
