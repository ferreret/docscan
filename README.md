<p align="center">
  <img src="resources/icons/docscan.svg" alt="DocScan Studio" width="120" height="120">
</p>

<h1 align="center">📄 DocScan Studio</h1>

<p align="center">
  <strong>Batch document capture, processing and indexing, with generative AI</strong>
</p>

<p align="center">
  <strong>English</strong> · <a href="README.es.md">Español</a>
</p>

<p align="center">
  <a href="https://github.com/ferreret/docscan/releases/latest"><img src="https://img.shields.io/badge/version-0.1.8-blue?style=flat-square" alt="Version"></a>
  <img src="https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.11-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/tests-1240_passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-72%25-yellowgreen?style=flat-square" alt="Coverage">
  <img src="https://img.shields.io/badge/license-proprietary-red?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Linux_%7C_Windows-lightgrey?style=flat-square" alt="Platform">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-documents-and-separators">Documents</a> •
  <a href="#-pipeline">Pipeline</a> •
  <a href="#-scripting">Scripting</a> •
  <a href="#-ai-mode">AI Mode</a> •
  <a href="https://ferreret.github.io/docscan/">Manual</a>
</p>

---

<p align="center">
  <img src="docs/screenshots/workbench_full.png" alt="DocScan Studio Workbench" width="860">
  <br>
  <em>Workbench: a batch of invoices split into documents by their barcode</em>
</p>

---

## 🎯 What is DocScan Studio?

DocScan Studio is a desktop application for **batch document capture** (scanner or
import). It processes each page (image, barcodes, OCR and scripts), lets the operator
review and **index** it, and transfers the result to the target archive.

It is a **multi-application environment**: the launcher holds N *applications*, each
one a processing profile with its own pipeline, fields, scripts and transfer, fully
independent of the others. Applications can be grouped by customer or department.

DocScan is the **cross-platform reimplementation** of FlexibarNET 10, Tecnomedia's
.NET capture product (Windows only) that runs in production in hospitals. It keeps
**functional parity** with it (same logic, same configuration keys, same tokens),
runs on Linux and Windows, and adds generative AI to create and configure
applications.

### Workflow

```
📥 Scan / import → 🔄 Pipeline (image · barcode · OCR · scripts) → ✅ Review and index → 📤 Transfer
```

### What's new in v0.1.8

- **Native document separator**: the batch is split into documents by barcode,
  automatically or by hand (Ctrl+D), as in FlexibarNET 10.
- **Per-document transfer**: one PDF, PDF/A or multipage TIFF per document, named by
  a pattern or by a script.
- **Configurator laid out like FlexibarNET 10**, with a syntax-highlighting script
  editor, and application **groups** in the launcher.
- Six real FlexibarNET 10 applications (the Hospital Arnau de Vilanova archive
  profiles) ported as the acceptance test.

Details in the [CHANGELOG](CHANGELOG.md) (in Spanish).

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🖨️ Capture
- Scanning through **SANE** (Linux) and **TWAIN / WIA** (Windows)
- Import of TIFF (including multipage), JPEG, PNG, BMP and PDF
- Automatic document feeder and blank page detection
- Unattended worker that watches an input folder

</td>
<td width="50%" valign="top">

### 🔄 Composable pipeline
- Image, barcode, OCR and script steps, in any order
- 24 image operations (deskew, crop, filters…)
- Flow control from scripts: skip, repeat, abort
- Pipeline test on a sample image

</td>
</tr>
<tr>
<td valign="top">

### 🔍 Recognition
- **Barcodes**: two engines (pyzbar and zxing-cpp), 15 symbologies
- **OCR**: RapidOCR, EasyOCR and Tesseract
- Reading on the whole page or in a zone, with a regex filter
- Manual barcode entry validated by regex

</td>
<td valign="top">

### 📑 Documents and indexing
- Barcode document separator, automatic or manual
- Batch fields (text, date, number, boolean, list)
- Page fields and a scriptable verification panel
- Review: flagged pages and navigation between them

</td>
</tr>
<tr>
<td valign="top">

### 📤 Transfer
- Folder, PDF, PDF/A, multipage TIFF or CSV
- One file per batch or per document
- Name by pattern or by script; on collision: suffix, overwrite or merge
- Everything is checked before writing; nothing is left half done

</td>
<td valign="top">

### 🐍 Python scripting
- 14 lifecycle events plus Script steps in the pipeline
- Full context: `app`, `batch`, `page`, `pipeline`
- Syntax-highlighting editor and editing in VS Code
- A failed script never counts as a success

</td>
</tr>
<tr>
<td valign="top">

### 🤖 Generative AI
- **AI Mode**: creates and edits applications from a conversation
- **Pipeline Assistant**: generates steps and event code
- Claude (Anthropic) or OpenAI, with keys encrypted with Fernet
- AI configures; processing each page stays deterministic

</td>
<td valign="top">

### 🌐 Interface
- Spanish (main language), English and Catalan
- Light and dark themes
- FlexibarNET 10 keyboard shortcuts
- Installers and automatic updates from GitHub

</td>
</tr>
</table>

---

## 🚀 Installation

### With the installer (recommended)

Download the latest version from [Releases](https://github.com/ferreret/docscan/releases/latest):

| System | File |
|--------|------|
| Linux (x86_64) | `docscan-0.1.8-x86_64.AppImage`: make it executable and open it |
| Windows | `docscan-0.1.8-setup.exe`: installer |

`SHA256SUMS.txt` holds the checksums. The application tells you when a new version is
out and updates itself. The database is created and migrated at startup.

### From source

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | **3.14** | If the system lacks it, `uv` installs it |
| ZBar | — | Linux only, used by pyzbar (`libzbar0t64` on Ubuntu) |
| SANE | — | Linux only, for scanning (`libsane-dev`) |
| libxcb-cursor | — | Linux only, Qt xcb platform (`libxcb-cursor0`) |
| Tesseract | 5.x | Optional, alternative OCR |

```bash
git clone https://github.com/ferreret/docscan.git
cd docscan
uv venv --python 3.14 --managed-python      # or: python3.14 -m venv .venv
uv pip install -r requirements.txt          # requirements-dev.txt adds tests and lint
.venv/bin/python main.py                    # Windows: .venv\Scripts\python.exe main.py
```

### Run modes

```bash
python main.py                                    # Launcher
python main.py "Supplier invoices"                # Open one application directly
python main.py --direct-mode "Supplier invoices"  # Scan and transfer with no UI

# Unattended worker
python -m docscan_worker --app-name "Supplier invoices" --watch /path/to/input
python -m docscan_worker --app-name "Supplier invoices" --process-pending
```

---

## 🖼️ Screenshots

<table>
<tr>
<td width="50%"><img src="docs/screenshots/launcher_dark.png" alt="Launcher with groups"><br><sub>Launcher with grouped applications</sub></td>
<td width="50%"><img src="docs/screenshots/configurator_transfer.png" alt="Configurator, Transfer tab"><br><sub>Transfer: one PDF per document, named by a script</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/dialog_barcode.png" alt="Barcode step with separator"><br><sub>Barcode step with its separator condition</sub></td>
<td><img src="docs/screenshots/ai_mode.png" alt="AI Mode"><br><sub>AI Mode: an application created from a conversation</sub></td>
</tr>
</table>

The screenshots show the interface in Spanish.

---

## 📑 Documents and separators

A **document** is the run of pages from one separator page to the next, as in
FlexibarNET 10. The separator is a property of the **page** (`page.is_separator` and
`page.separator_value`), not of a barcode. Pages before the first separator form an
implicit document.

The usual case needs no script:

1. In the **Barcode** step, turn on the document separator and set its condition. For
   example, the regex `^(02|10)` evaluated on *NN + value* marks as a separator every
   page with a Code128 or an Interleaved 2 of 5 (the symbology numbers are
   FlexibarNET's). On reprocessing, detection overrides the manual mark.
2. In **Transfer**: mode `pdf`, `pdfa` or `tiff`, one file per document, and a
   pattern with `{separator}`, `{document_index}` or `{document_id}`. The separator
   page can stay in the document (as its cover) or be dropped.
3. With the *merge* collision policy, a document whose name already exists is
   appended to that file: pages with the same code end up together even when they
   arrive in another batch.

In the Workbench, **Ctrl+D** marks or unmarks the page as a separator (with its
value, validated against the step's manual regex) and **Alt+↑ / Alt+↓** move it.

When the name needs logic, the **name script** computes it:

```python
def file_name(page, document, batch, app):
    from datetime import datetime

    date = datetime.strptime(batch.fields["Data"], "%d/%m/%Y")
    return f"{date:%Y%m%d}/{document.separator_value[-9:]}"  # no extension
```

Returning `None` falls back to the pattern; if the script raises, the transfer does
not run and nothing is written. The Hospital Arnau de Vilanova archive applications
ported from FlexibarNET 10 are a complete example (`tools/arnau_apps.py`).

---

## 🔄 Pipeline

Every page goes through a sequence of steps configured per application:

```
┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐
│ ImageOp  │──▶│   Barcode    │──▶│   OCR    │──▶│  Script  │
│ Deskew   │   │ Engine 1 / 2 │   │ RapidOCR │   │ Python   │
│ Crop     │   │ + separator  │   │          │   │          │
└──────────┘   └──────────────┘   └──────────┘   └──────────┘
```

| Type | Description |
|------|-------------|
| `image_op` | One operation on the image (24 available) |
| `barcode` | Barcode reading (2 engines, 15 symbologies) and separator condition |
| `ocr` | Text recognition (3 engines) |
| `script` | Python with the full context |

<details>
<summary>📋 The 24 image operations</summary>

| Operation | Description |
|-----------|-------------|
| `AutoDeskew` | Automatic skew correction |
| `ConvertTo1Bpp` | Black and white (1 bit) |
| `Crop` | Rectangular crop |
| `CropWhiteBorders` / `CropBlackBorders` | Automatic margin crop |
| `Resize` | Resize |
| `Rotate` / `RotateAngle` | Rotate by 90°/180°/270° or by an angle |
| `SetBrightness` / `SetContrast` | Brightness and contrast |
| `RemoveLines` | Remove horizontal and vertical lines |
| `FxDespeckle` | Remove noise |
| `FxGrayscale` / `FxNegative` | Grayscale / negative |
| `FxDilate` / `FxErode` | Dilation and erosion |
| `FxEqualizeIntensity` | Histogram equalization |
| `FloodFill` | Flood fill |
| `RemoveHolePunch` | Remove punch holes |
| `SetResolution` | Set the DPI |
| `SwapColor` | Swap colors |
| `KeepChannel` / `RemoveChannel` / `ScaleChannel` | Per color channel operations |

</details>

<details>
<summary>📊 Barcode symbologies</summary>

| Symbology | Engine 1 (pyzbar) | Engine 2 (zxing-cpp) |
|-----------|:-:|:-:|
| Code128, Code39, Code93, Codabar | ✅ | ✅ |
| EAN-13, EAN-8, UPC-A, UPC-E | ✅ | ✅ |
| ITF (Interleaved 2 of 5) | ✅ | ✅ |
| QR, PDF417, DataMatrix | ✅ | ✅ |
| Aztec, MaxiCode, Micro QR | — | ✅ |

</details>

### Flow control from scripts

```python
def my_step(app, batch, page, pipeline):
    if not page.barcodes:
        pipeline.repeat_step("codes")        # at most 3 times
    if not page.ocr_text and not page.barcodes:
        pipeline.abort("Page with no text and no codes")   # sent to review
    pipeline.skip_to("final")                # or skip_step("ocr")
    pipeline.set_metadata("kind", "invoice") # data shared by this page's steps
```

---

## 🐍 Scripting

| Object | Description | Available in |
|--------|-------------|--------------|
| `app` | Application configuration | All |
| `batch` | Current batch and its fields | All |
| `page` | Page: image, `barcodes`, `ocr_text`, `fields`, separator | Steps and page events |
| `pipeline` | Flow control | Script steps only |
| `log` | Script logger | All |
| `re`, `json`, `datetime`, `Path`, `ImageLib` | Standard modules and image utilities | All |

**14 events** outside the pipeline: `on_app_start`, `on_app_end`, `on_import`,
`on_scan_complete`, `on_batch_loaded`, `on_page_changed`, `on_transfer_validate`,
`on_transfer_advanced`, `on_transfer_page`, `on_navigate_prev`, `on_navigate_next`,
`on_navigate_script`, `on_key_event` and `init_global`. Their signatures are in the
[scripting reference](https://ferreret.github.io/docscan/reference/scripting-api/)
(in Spanish).

```python
# on_transfer_validate: returning False or raising cancels the transfer
def on_transfer_validate(app, batch, pages):
    no_code = [p.page_index + 1 for p in pages if not p.is_separator]
    if no_code:
        # ValueError = rejection: the operator sees only this message
        raise ValueError(f"Page {no_code[0]} has no code")
    return True
```

Scripts are compiled once when the application loads, and can be edited in VS Code
with autocompletion.

---

## 🤖 AI Mode

A conversational assistant in the launcher that **creates and edits applications**
in natural language through *tool calling*: it generates the pipeline, fields,
scripts and transfer, and tests the pipeline on a sample image. The **Pipeline
Assistant** does the same inside the configurator for a single application.

```
👤 I need an application for supplier invoices: one PDF per invoice,
   split by the Code128 on the first page.

🤖 I created "Supplier invoices": deskew → barcodes → OCR. The barcode
   step marks as a separator every page with a Code128 starting with FAC-,
   and the transfer writes one PDF per invoice named after its number.
   Anything else to adjust?
```

---

## 📋 Configurator

| Tab | Contents |
|-----|----------|
| ⚙️ **General** | Name, description, group, icon color, scanner, auto-transfer, blank pages |
| 🖼️ **Image** | Capture format, color mode, compression |
| 📝 **Batch fields** | Master-detail field editor: type, required, description, values |
| 🔄 **Pipeline** | Step list with a summary of each; one dialog per step type |
| 📜 **Events** | The 14 events and the verification panel in a list, with status and an "enabled" box |
| 📤 **Transfer** | Mode, destination, collision, name (pattern or script) and per-document grouping |
| 🔔 **Notifications** | Webhook when a transfer ends or fails |

---

## ⌨️ Keyboard shortcuts

Capture shortcuts are FlexibarNET 10's. The main ones:

| Shortcut | Action |
|----------|--------|
| `F5` / `Ctrl+I` | Scan / import |
| `F9` / `Ctrl+P` | Process the batch / reprocess the page |
| `Ctrl+T` / `Ctrl+W` | Transfer / close the batch |
| `Ctrl+D` | Mark or unmark a document separator |
| `Alt+↑` / `Alt+↓` | Move the page |
| `Ctrl+N` / `Insert` | Add a barcode by hand |
| `Ctrl+→` / `Ctrl+Shift+→` | Next page with a barcode / pending review |

The full list is in the [manual](https://ferreret.github.io/docscan/reference/shortcuts/).

---

## 🔒 Reliability and security

- **Nothing fails silently**, as in FlexibarNET 10: a failing script shows up on the
  page, in the log or as a failed transfer, never as a success.
- **The transfer checks before writing**: names, paths and images. Multipage files
  are written atomically.
- **Hardened paths**: a value read from paper cannot write outside the destination.
- **API keys encrypted** with Fernet in `secrets.enc`, in the user's configuration
  directory.
- **SQLite in WAL mode**, so the UI and the worker can run at the same time;
  migrations apply themselves at startup.
- **Time limit** of 30 s for pipeline Script steps.

---

## 📁 Formats

| Input | Output |
|-------|--------|
| TIFF (including multipage), JPEG, PNG, BMP, PDF | TIFF (LZW, ZIP, uncompressed or Group4 for B/W), JPEG, PNG, PDF, PDF/A-1b and 2b, index CSV |

In a multipage TIFF, Group4 is used only when every page is black and white; if any
page is gray or color, the file is written in LZW (as in FlexibarNET 10).

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  🏠 Launcher  │  ⚙️ Configurator  │  📋 Workbench  │  📂 Batches   │
├──────────────────────────────────────────────────────────────────┤
│  Services: ScriptEngine · Barcode · ImagePipeline · OCR ·         │
│  Transfer (+ transfer_flow) · Batch · Import · Scanner · AI       │
├──────────────────────────────────────────────────────────────────┤
│  Pipeline: steps → PipelineContext → executor → separator        │
├──────────────────────────────────────────────────────────────────┤
│  Persistence: SQLAlchemy 2 · SQLite WAL · Alembic                 │
└──────────────────────────────────────────────────────────────────┘
        ▲                                         ▲
   QThread workers (scan, recognition,         docscan_worker
   transfer): the UI never blocks              (unattended)
```

```
docscan/
├── app/
│   ├── db/              # Engine, repositories and startup migrations
│   ├── models/          # ORM models and the logical document
│   ├── pipeline/        # Steps, context, executor, serializer, separator
│   ├── services/        # Barcode, OCR, image, transfer, scripts, AI…
│   ├── ui/              # Launcher, Configurator, Workbench, batch manager
│   └── workers/         # QThreads for scanning, recognition and transfer
├── docscan_worker/      # Unattended worker (watched folder / pending batches)
├── config/              # Settings (pydantic) and secrets (Fernet)
├── alembic/             # Migrations
├── resources/           # Icons, QSS styles, translations
├── tools/               # Screenshots, Arnau applications, desktop entry
├── docs-web/            # Manual (MkDocs)
└── tests/               # pytest + pytest-qt
```

---

## 🧪 Tests and quality

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q   # no windows, ~35 s
.venv/bin/ruff check .
```

| Metric (v0.1.8) | Value |
|-----------------|-------|
| Automated tests | **1240**, 0 failures |
| Line coverage | **72%** (`app/` + `docscan_worker/`) |
| Python lines in `app/` | 27,407 |
| Test lines | 18,743 |

The suite needs no scanner or display and never touches the user's configuration. It
includes end-to-end tests through the real worker with real barcodes. GitHub Actions
runs lint and tests on every push to `main` and on every pull request. How each
figure was measured: [`docs/portfolio/metricas.md`](docs/portfolio/metricas.md)
(in Spanish).

---

## 📚 Documentation

- **[User manual](https://ferreret.github.io/docscan/)** (in Spanish): launcher,
  configurator, pipeline, workbench, transfer and scripting.
- **[CHANGELOG](CHANGELOG.md)**: changes in each version.
- **[Document separator design](docs/diseno_separadores_documento_2026-10-26.md)** and
  **[proposals from FlexibarNET 10](docs/propuestas_desde_flexibarnet10_2026-10-26.md)**
  (in Spanish).

---

## 🗺️ Roadmap

Done: composable pipeline, two barcode engines, three OCR engines, AI (AI Mode and
Pipeline Assistant), scripting, workbench, batch manager, unattended worker, three
languages, installers with automatic updates, web manual, fail-closed transfer and
the document separator.

Next:

- [ ] Hospital Arnau eCAP family: secrets available to scripts and registration over
      ODBC.
- [ ] Roll back a transfer that fails halfway.
- [ ] Log to file, with personal data masked.
- [ ] Rest of the separator work: `{pagefield:}`, dragging thumbnails, document headers.
- [ ] Validation with a physical scanner on Linux.

---

## 🌐 Web version (archived)

The repository holds a multi-tenant web version (`web/`: FastAPI API, ARQ worker,
PostgreSQL, MinIO and Redis). **It has been archived since July 2026** and is not
maintained; its tests skip themselves when their dependencies are missing.

---

## 👥 Credits

Developed by **Tecnomedia**, document management solutions.

<p align="center">
  <sub>DocScan Studio v0.1.8</sub>
</p>
