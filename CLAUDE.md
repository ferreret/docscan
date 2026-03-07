# CLAUDE.md — DocScan Studio

Aplicación de escritorio PySide6 inspirada en Flexibar.NET. Framework multi-aplicación para captura, procesamiento e indexación masiva de documentos con soporte de IA generativa.

---

## Concepto central

El sistema NO es una sola aplicación monolítica. Es un **framework de aplicaciones**:
- El **Launcher** lista N "aplicaciones" (perfiles de proceso)
- Cada **aplicación** tiene configuración completamente independiente: pipeline, scripts, transferencia, IA
- El **Workbench** es la ventana de explotación que carga y ejecuta una aplicación concreta

---

## Stack y versiones

- **Python**: 3.14 (en Xubuntu invocar como `python3.14`)
- **UI**: PySide6
- **ORM**: SQLAlchemy 2.x
- **BD**: SQLite en **WAL mode** (obligatorio — concurrencia UI + DocScanWorker)
- **Barcode**: `pyzbar` + `opencv-python` (Motor 1), `zxing-cpp` (Motor 2)
- **Pipeline imagen**: `opencv-python` + `Pillow`
- **OCR principal**: `rapidocr-onnxruntime` (sin PyTorch, modelos ~10MB)
- **OCR alternativo**: `easyocr` (mayor precisión, modelos ~500MB, requiere PyTorch)
- **OCR fallback**: `pytesseract`
- **IA**: `anthropic` SDK, `openai` SDK
- **Escáner TWAIN**: `pytwain` (Windows; riesgo: drivers 32-bit — ver nota)
- **Escáner WIA**: `pywin32` (`win32com`) — alternativa moderna sin problemas 64-bit
- **PDF**: `pymupdf` (fitz) — entrada y salida incluida PDF/A
- **HTTP**: `httpx`
- **Email**: `smtplib` stdlib
- **Folder-watch**: `watchdog`
- **Scheduler**: `APScheduler`
- **Cifrado**: `cryptography` (Fernet)
- **Config**: `pydantic-settings`
- **Testing**: `pytest`, `pytest-qt`

> **Nota TWAIN**: con Python 64-bit, muchos drivers de escáner solo tienen DSM de 32-bit. Si el escáner no aparece en la lista, instalar el TWAIN DSM 64-bit de twain.org o usar WIA como alternativa.

---

## Pipeline de procesado — Arquitectura central

### Concepto

El procesado de cada página es un **pipeline dinámico y composable**. Cada aplicación define su pipeline como una lista ordenada de pasos. Un paso puede ser:

- Una **operación de imagen** (`ImageOp`): deskew, crop, threshold, rotate, etc.
- Una **lectura de barcode** (`BarcodeStep`): Motor 1 o Motor 2
- Una **llamada a OCR** (`OcrStep`): EasyOCR o Tesseract
- Una **llamada a IA** (`AiStep`): Claude Vision, GPT-4o
- Un **script de usuario** (`ScriptStep`): Python arbitrario con acceso al contexto completo

El pipeline se almacena en la BD como JSON y se edita desde la UI como una lista de pasos (no requiere un diseñador visual complejo, basta un editor de lista con formularios por tipo de paso).

### Definición del pipeline (JSON)

```json
[
  {
    "id": "step_001",
    "type": "image_op",
    "enabled": true,
    "op": "AutoDeskew"
  },
  {
    "id": "step_002",
    "type": "image_op",
    "enabled": true,
    "op": "ConvertTo1Bpp",
    "params": { "threshold": 128 }
  },
  {
    "id": "step_003",
    "type": "barcode",
    "enabled": true,
    "engine": "motor1",
    "symbologies": ["Code128", "Code39", "QR"],
    "regex": "^\\d{8}$",
    "regex_include_symbology": false,
    "orientations": ["horizontal", "vertical"],
    "window": null
  },
  {
    "id": "step_004",
    "type": "script",
    "enabled": true,
    "label": "Clasificar barcodes leídos",
    "entry_point": "classify_barcodes",
    "script": "def classify_barcodes(app, batch, page, pipeline):\n    # El script decide qué rol tiene cada barcode\n    for bc in page.barcodes:\n        if bc.value.startswith('SEP-'):\n            bc.role = 'separator'\n        else:\n            bc.role = 'content'\n    # Si no hay separador, marcar para revisión\n    if not any(bc.role == 'separator' for bc in page.barcodes):\n        page.flags.needs_review = True\n"
  },
  {
    "id": "step_005",
    "type": "barcode",
    "enabled": true,
    "engine": "motor2",
    "symbologies": ["QR", "DataMatrix", "PDF417"],
    "regex": "",
    "orientations": ["horizontal", "vertical", "diagonal"],
    "window": null
  },
  {
    "id": "step_006",
    "type": "image_op",
    "enabled": true,
    "op": "FxDespeckle"
  },
  {
    "id": "step_007",
    "type": "ocr",
    "enabled": true,
    "engine": "easyocr",
    "languages": ["es", "en"],
    "full_page": true
  },
  {
    "id": "step_008",
    "type": "script",
    "enabled": true,
    "label": "Filtro pre-IA por valor barcode",
    "entry_point": "before_ai",
    "script": "def before_ai(app, batch, page, pipeline):\n    # Solo llamar a IA si se leyó algún barcode\n    if not page.barcodes:\n        pipeline.skip_step('step_009')\n"
  },
  {
    "id": "step_009",
    "type": "ai",
    "enabled": true,
    "provider": "anthropic",
    "template_id": 3,
    "fallback_provider": "local_ocr"
  },
  {
    "id": "step_010",
    "type": "script",
    "enabled": true,
    "label": "Validación final de campos",
    "entry_point": "validate_fields",
    "script": "def validate_fields(app, batch, page, pipeline):\n    if not page.ai_fields.get('numero_factura'):\n        page.flags.needs_review = True\n        page.flags.review_reason = 'Falta número de factura'\n"
  }
]
```

### Modelos del pipeline

```python
# app/pipeline/steps.py

from dataclasses import dataclass, field
from typing import Any, Literal

StepType = Literal["image_op", "barcode", "ocr", "ai", "script"]

@dataclass
class PipelineStep:
    id: str
    type: StepType
    enabled: bool = True

@dataclass
class ImageOpStep(PipelineStep):
    type: Literal["image_op"] = "image_op"
    op: str = ""                      # Nombre de la operación
    params: dict[str, Any] = field(default_factory=dict)
    window: tuple[int,int,int,int] | None = None  # (x, y, w, h) en píxeles

@dataclass
class BarcodeStep(PipelineStep):
    """
    Lee códigos de barras de la imagen actual y los añade a page.barcodes.
    No distingue entre separadores o contenido — esa semántica la decide
    el ScriptStep siguiente si es necesario.
    Cada ejecución de este paso ACUMULA resultados en page.barcodes;
    no reemplaza los de pasos anteriores.
    """
    type: Literal["barcode"] = "barcode"
    engine: Literal["motor1", "motor2"] = "motor1"
    symbologies: list[str] = field(default_factory=list)  # [] = todas
    regex: str = ""                                        # "" = sin filtro
    regex_include_symbology: bool = False                  # prefijo 2 dígitos de simbología
    orientations: list[str] = field(default_factory=lambda: ["horizontal", "vertical"])
    quality_threshold: float = 0.0
    window: tuple[int,int,int,int] | None = None           # None = página completa

@dataclass
class OcrStep(PipelineStep):
    type: Literal["ocr"] = "ocr"
    engine: Literal["easyocr", "tesseract"] = "easyocr"
    languages: list[str] = field(default_factory=lambda: ["es"])
    full_page: bool = True
    window: tuple[int,int,int,int] | None = None  # None = página completa

@dataclass
class AiStep(PipelineStep):
    type: Literal["ai"] = "ai"
    provider: Literal["anthropic", "openai", "local_ocr"] = "anthropic"
    template_id: int | None = None
    fallback_provider: str | None = None

@dataclass
class ScriptStep(PipelineStep):
    type: Literal["script"] = "script"
    label: str = ""          # Nombre descriptivo visible en la UI
    entry_point: str = ""    # Nombre de la función Python a llamar
    script: str = ""         # Código Python del script
```

### PipelineContext — Control de flujo desde los scripts

El objeto `pipeline` que reciben los `ScriptStep` expone control de flujo:

```python
# app/pipeline/context.py

class PipelineContext:
    """
    Pasado a cada ScriptStep. Permite al script controlar
    la ejecución del pipeline de forma declarativa.
    """

    def skip_step(self, step_id: str) -> None:
        """Salta un paso específico por su id."""

    def skip_to(self, step_id: str) -> None:
        """Salta todos los pasos hasta llegar a step_id (inclusive)."""

    def abort(self, reason: str = "") -> None:
        """Detiene el pipeline para esta página. Marca página con needs_review."""

    def repeat_step(self, step_id: str) -> None:
        """Re-ejecuta un paso ya ejecutado (útil para reintentos)."""

    def replace_image(self, image: np.ndarray) -> None:
        """Reemplaza la imagen en curso (por ejemplo tras un procesado custom)."""

    def get_step_result(self, step_id: str) -> Any:
        """Obtiene el resultado de un paso ya ejecutado."""

    def set_metadata(self, key: str, value: Any) -> None:
        """Almacena metadatos accesibles en pasos posteriores del pipeline."""

    def get_metadata(self, key: str) -> Any:
        """Recupera metadatos establecidos previamente."""
```

### Executor del pipeline

```python
# app/pipeline/executor.py

class PipelineExecutor:
    """
    Ejecuta el pipeline de pasos para una página concreta.
    Cada aplicación crea su propio executor con su pipeline configurado.
    """

    def __init__(
        self,
        steps: list[PipelineStep],
        barcode_service: BarcodeService,
        image_pipeline: ImagePipelineService,
        ai_service: AiService,
        ocr_service: OcrService,
        script_engine: ScriptEngine,
    ): ...

    def execute(self, page: PageContext, batch: BatchContext, app: AppContext) -> PageContext:
        """
        Ejecuta todos los pasos habilitados en orden.
        Los ScriptStep pueden modificar el flujo vía PipelineContext.
        Captura errores de pasos individuales sin detener el pipeline
        (salvo que el script llame a pipeline.abort()).
        """
        pipeline_ctx = PipelineContext(steps=self._steps)
        
        while pipeline_ctx.has_next():
            step = pipeline_ctx.next_step()
            
            if not step.enabled:
                continue
            
            try:
                self._execute_step(step, page, batch, app, pipeline_ctx)
            except StepError as e:
                self._log.error(f"Error en paso {step.id} ({step.type}): {e}")
                if step.type != "script":
                    # Los errores en pasos de procesado no detienen el pipeline
                    page.flags.processing_errors.append(str(e))
        
        return page
```

### ScriptEngine — Ejecución de scripts de usuario

```python
# app/services/script_engine.py

class ScriptEngine:
    """
    Compila y ejecuta scripts Python de usuario de forma segura.
    - Compila el código una vez al cargar la aplicación (cache por step_id)
    - Captura TODAS las excepciones sin crashear la app
    - Expone el contexto completo al script
    """

    def __init__(self):
        self._compiled_cache: dict[str, CodeType] = {}

    def compile_step(self, step: ScriptStep) -> None:
        """Pre-compila el script al cargar la aplicación."""
        try:
            code = compile(step.script, f"<script:{step.label}>", "exec")
            self._compiled_cache[step.id] = code
        except SyntaxError as e:
            raise ScriptCompilationError(f"Error de sintaxis en '{step.label}': {e}")

    def run_step(
        self,
        step: ScriptStep,
        page: PageContext,
        batch: BatchContext,
        app: AppContext,
        pipeline: PipelineContext,
    ) -> None:
        """Ejecuta el entry point del step."""
        code = self._compiled_cache.get(step.id)
        if not code:
            return

        namespace = self._build_namespace(page, batch, app, pipeline)
        try:
            exec(code, namespace)
            func = namespace.get(step.entry_point)
            if func and callable(func):
                func(app=app, batch=batch, page=page, pipeline=pipeline)
        except Exception as e:
            self._log.error(f"Error ejecutando '{step.entry_point}': {e}")
            page.flags.script_errors.append({
                "step_id": step.id,
                "entry_point": step.entry_point,
                "error": str(e),
            })

    def _build_namespace(self, page, batch, app, pipeline) -> dict:
        return {
            "app": app,
            "batch": batch,
            "page": page,
            "pipeline": pipeline,
            "log": self._log,
            "http": self._http_client,
            "re": __import__("re"),
            "json": __import__("json"),
            "datetime": __import__("datetime"),
            "Path": __import__("pathlib").Path,
        }
```

---

## Entry points de aplicación (distintos del pipeline)

Además de los `ScriptStep` dentro del pipeline, cada aplicación tiene entry points de ciclo de vida (almacenados en la pestaña Eventos):

| Entry point | Cuándo |
|-------------|--------|
| `on_app_start(app, batch)` | Al abrir la aplicación |
| `on_app_end(app, batch)` | Al cerrar la aplicación |
| `on_import(app, batch)` | Al pulsar Procesar (reemplaza carga estándar si está definido) |
| `on_scan_complete(app, batch)` | Al terminar carga + todo el pipeline |
| `on_transfer_validate(app, batch) -> bool` | Antes de transferir; False cancela |
| `on_transfer_advanced(app, batch, result)` | Transferencia avanzada scripteada |
| `on_transfer_page(app, batch, page, result)` | Post-copia por página |
| `on_navigate_prev(app, batch, page) -> int` | Navegación previa programable |
| `on_navigate_next(app, batch, page) -> int` | Navegación siguiente programable |
| `on_key_event(app, batch, page, key)` | Tecla personalizada |
| `init_global(app)` | Al iniciar el programa (script global del launcher) |

> Toda la lógica de reconocimiento (barcode, OCR, IA, validaciones intermedias) va en `ScriptStep` dentro del pipeline. Los entry points de ciclo de vida son solo para inicio/fin/transferencia/navegación.

Estos entry points se gestionan en la pestaña **Eventos** del configurador y se ejecutan fuera del pipeline.

---

## UI del pipeline (sin diseñador visual complejo)

La UI para el pipeline es un **editor de lista** en la pestaña "Pipeline" del configurador:

```
┌─────────────────────────────────────────────────────────┐
│ Pipeline de procesado                    [+ Añadir paso] │
├─────┬──────────────────────────┬────────┬───────────────┤
│ ☑  │ 🖼 AutoDeskew             │ imagen │ [✏] [🗑] [↑↓] │
│ ☑  │ 🖼 ConvertTo1Bpp (128)    │ imagen │ [✏] [🗑] [↑↓] │
│ ☑  │ 📊 Barcode M1 · Code128   │ barcode│ [✏] [🗑] [↑↓] │
│ ☑  │ 📝 Clasificar barcodes    │ script │ [✏] [🗑] [↑↓] │
│ ☑  │ 📊 Barcode M2 · QR/DM     │ barcode│ [✏] [🗑] [↑↓] │
│ ☑  │ 🤖 IA → Plantilla Factura │ ai     │ [✏] [🗑] [↑↓] │
│ ☑  │ 📝 Validar campos IA      │ script │ [✏] [🗑] [↑↓] │
└─────┴──────────────────────────┴────────┴───────────────┘
```

- Checkbox para habilitar/deshabilitar cada paso sin borrarlo
- Botón [✏] abre un diálogo con el formulario del paso (distinto por tipo)
- Los pasos de tipo `script` abren el editor de código Python
- Reordenar con botones ↑↓ o drag & drop
- El formulario de `script` incluye: label, entry_point, editor de código con syntax highlighting

---

## Estructura del proyecto

```
docscan/
├── main.py
├── app/
│   ├── ui/
│   │   ├── launcher/               # Diálogo principal + gestor de apps
│   │   ├── workbench/              # Ventana de explotación de una aplicación
│   │   │   ├── main_workbench.py
│   │   │   ├── thumbnail_panel.py
│   │   │   ├── document_viewer.py
│   │   │   ├── barcode_panel.py
│   │   │   └── metadata_panel.py
│   │   ├── configurator/
│   │   │   ├── app_configurator.py
│   │   │   ├── tabs/
│   │   │   │   ├── tab_general.py
│   │   │   │   ├── tab_batch_fields.py
│   │   │   │   ├── tab_indexing.py
│   │   │   │   ├── tab_pipeline.py      # ← Editor de lista de pasos
│   │   │   │   ├── tab_events.py        # ← Entry points de ciclo de vida
│   │   │   │   ├── tab_transfer.py
│   │   │   │   └── tab_batch_mode.py
│   │   │   ├── step_dialogs/            # Un diálogo por tipo de paso del pipeline
│   │   │   │   ├── image_op_dialog.py
│   │   │   │   ├── barcode_step_dialog.py
│   │   │   │   ├── ocr_step_dialog.py
│   │   │   │   ├── ai_step_dialog.py
│   │   │   │   └── script_step_dialog.py
│   │   │   └── script_editor.py         # Widget editor Python reutilizable
│   │   ├── batch_manager/
│   │   └── template_designer/
│   ├── pipeline/
│   │   ├── steps.py                     # Dataclasses de todos los tipos de paso
│   │   ├── context.py                   # PipelineContext (control de flujo)
│   │   ├── executor.py                  # PipelineExecutor
│   │   └── serializer.py                # JSON ↔ list[PipelineStep]
│   ├── services/
│   │   ├── scanner_service.py
│   │   ├── barcode_service.py
│   │   ├── image_pipeline.py            # Implementación de cada ImageOp
│   │   ├── ai_service.py
│   │   ├── ocr_service.py
│   │   ├── script_engine.py
│   │   ├── transfer_service.py
│   │   └── batch_service.py
│   ├── providers/
│   │   ├── base_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   └── local_ocr_provider.py
│   ├── models/
│   │   ├── application.py
│   │   ├── batch.py
│   │   ├── page.py
│   │   ├── barcode.py
│   │   └── template.py
│   ├── workers/
│   │   ├── scan_worker.py
│   │   ├── recognition_worker.py        # Usa PipelineExecutor por página
│   │   └── transfer_worker.py
│   └── db/
│       ├── database.py
│       ├── repositories/
│       └── migrations/
├── config/
│   ├── settings.py
│   └── secrets.py
├── docscan_worker/
│   └── worker_main.py
├── tests/
└── resources/
    ├── styles/
    └── icons/
```

---

## Convenciones

### General
- Clases: `PascalCase` | funciones/variables: `snake_case` | constantes: `UPPER_SNAKE_CASE`
- UI en español | docstrings en español, Google style
- Type hints obligatorios en funciones públicas

### PySide6
- Operaciones lentas → siempre `QThread`; nunca bloquear el hilo de UI
- Comunicar resultados con `Signal`
- Estilos en `.qss` en `resources/styles/`

### Pipeline
- El `PipelineExecutor` es stateless entre páginas; crear una instancia por aplicación
- Compilar todos los `ScriptStep` al cargar la aplicación (no en cada ejecución)
- Un error en un `ScriptStep` no detiene el pipeline; se registra en `page.flags.script_errors`
- El JSON del pipeline se almacena en la columna `pipeline_json` de la tabla `applications`
- `pipeline/serializer.py` implementa `serialize(steps) -> str` y `deserialize(json_str) -> list[PipelineStep]`

### Seguridad
- API keys cifradas con Fernet en `~/.docscan/secrets.enc`
- Nunca loguear API keys ni contenido de documentos sensibles
- Rutas con `pathlib.Path` y `platformdirs`

---

## Patrones obligatorios

### BD — WAL mode (obligatorio)

SQLite debe arrancar siempre en WAL mode para permitir concurrencia entre la UI y el `DocScanWorker`:

```python
# app/db/database.py
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")
```

### Límite de repeat_step (obligatorio)

```python
# app/pipeline/executor.py
MAX_STEP_REPEATS: int = 3  # configurable en settings

# Dentro del PipelineExecutor:
if self._repeat_counts[step.id] >= self._max_repeats:
    raise PipelineAbortError(
        f"Paso '{step.id}' superó el límite de {self._max_repeats} repeticiones"
    )
self._repeat_counts[step.id] += 1
```

### Escáner — abstracción TWAIN/WIA

```python
# app/services/scanner_service.py
class BaseScanner(ABC):
    @abstractmethod
    def list_sources(self) -> list[str]: ...
    @abstractmethod
    def acquire(self, source: str, config: ScanConfig) -> list[np.ndarray]: ...

class TwainScanner(BaseScanner): ...   # pytwain
class WiaScanner(BaseScanner): ...    # pywin32 / win32com
```

La selección TWAIN/WIA es configurable por aplicación. Si TWAIN falla al listar fuentes, ofrecer WIA automáticamente.

### Worker QThread

```python
class RecognitionWorker(QThread):
    page_processed = Signal(int, object)   # (índice, PageContext)
    all_done = Signal()
    error_occurred = Signal(str)
    progress_updated = Signal(int)

    def run(self):
        try:
            for i, page in enumerate(self._pages):
                result = self._executor.execute(page, self._batch, self._app)
                self.page_processed.emit(i, result)
                self.progress_updated.emit(int((i+1) / len(self._pages) * 100))
            self.all_done.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))
```

### Proveedor IA (Strategy)

```python
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def extract_fields(self, image_b64: str, template: Template) -> dict[str, str]: ...

    @abstractmethod
    def classify_document(self, image_b64: str, classes: list[str]) -> str: ...
```

### Repositorio

```python
class ApplicationRepository:
    def __init__(self, session: Session): ...
    def get_all_active(self) -> list[Application]: ...
    def get_by_id(self, app_id: int) -> Application | None: ...
    def save(self, app: Application) -> Application: ...
    def delete(self, app_id: int) -> None: ...
```

---

## Lo que NO hacer

- ❌ No bloquear el hilo de UI (`time.sleep()`, operaciones síncronas pesadas)
- ❌ No almacenar API keys en texto plano
- ❌ No mezclar lógica de negocio dentro de widgets PySide6
- ❌ No usar `print()` para logging; usar `logging` stdlib
- ❌ No crear sesiones SQLAlchemy fuera de context manager
- ❌ No compilar scripts de usuario en cada ejecución de página; cachear por `step.id`
- ❌ No dejar que un error en un script detenga el pipeline ni crashee la app
- ❌ No hardcodear rutas; usar `pathlib.Path` y `platformdirs`
- ❌ No usar SQLite sin WAL mode; la concurrencia UI + DocScanWorker puede corromper datos
- ❌ No llamar a `pipeline.repeat_step()` sin condición de salida; el executor tiene límite pero el script debe tenerlo también
- ❌ No distinguir "barcode separador" vs "barcode contenido" en el motor; esa semántica es del script
- ❌ No referenciar `barcodes` como objeto de contexto independiente; siempre es `page.barcodes`

---

## Orden de implementación

1. `app/pipeline/steps.py` — dataclasses de todos los tipos de paso (incluidos `condition` y `http_request`)
2. `app/pipeline/context.py` — `PipelineContext` con control de flujo y límite de `repeat_step`
3. `app/pipeline/serializer.py` — JSON ↔ `list[PipelineStep]`
4. `config/settings.py` + `config/secrets.py`
5. `app/db/database.py` — SQLite con WAL mode + repositorios
6. `app/models/` — modelos de dominio
7. `app/services/script_engine.py` — compilación y ejecución de scripts
8. `app/services/image_pipeline.py` — implementación de todas las `ImageOp`
9. `app/services/barcode_service.py` — Motor 1 (pyzbar) + Motor 2 (zxing-cpp)
10. `app/providers/` + `app/services/ai_service.py` + `app/services/ocr_service.py` (RapidOCR primero)
11. `app/pipeline/executor.py` — `PipelineExecutor` con límite de repeticiones
12. `app/services/scanner_service.py` — BaseScanner + TwainScanner + WiaScanner
13. `app/services/import_service.py` — importación de imágenes y PDFs
14. `app/services/batch_service.py` + `app/services/transfer_service.py`
15. `app/services/notification_service.py` — webhooks + email
16. `app/ui/launcher/` — launcher con lista de aplicaciones y descarga de modelos
17. `app/ui/configurator/tabs/tab_pipeline.py` — editor de lista de pasos + botón Probar
18. `app/ui/configurator/step_dialogs/` — formularios por tipo de paso
19. `app/ui/configurator/tabs/tab_events.py` — entry points de ciclo de vida
20. `app/ui/workbench/` — interfaz de explotación completa
21. `app/ui/batch_manager/` — gestión de lotes con estadísticas
22. `docscan_worker/worker_main.py` + `docscan_worker/folder_watcher.py`
23. `tests/`

---

## Entorno de desarrollo

```bash
# Primera vez: crear entorno virtual y activarlo
python3.14 -m venv .venv
source .venv/bin/activate

# Actualizar pip e instalar dependencias (dentro del venv)
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-qt ruff  # herramientas de desarrollo

# Activar en sesiones posteriores
source .venv/bin/activate
```

> Todas las herramientas (`pytest`, `ruff`, `alembic`) deben ejecutarse con el venv activo para que usen el intérprete correcto y las dependencias del proyecto.

## Comandos

```bash
# Crear entorno virtual
python3.14 -m venv .venv && source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python3.14 main.py

# Lanzar directamente una aplicación
python3.14 main.py "Nombre de la Aplicación"

# Modo directo (sin UI)
python3.14 main.py --direct-mode "Nombre de la Aplicación"

# Proceso desatendido
python3.14 -m docscan_worker --batch-path /ruta/lotes

# Tests
pytest tests/ -v --tb=short

# Migraciones BD
alembic upgrade head
alembic revision --autogenerate -m "descripcion"

# Lint
ruff check app/
ruff format app/
```
