# DocScan Studio — Requerimientos del Proyecto
*Versión 3.0 — Revisión de viabilidad aplicada*

> **Cambios respecto a v2.0**: Secciones 3.5 y 3.6 (Barcode Separador/Contenido) eliminadas — absorbidas por el pipeline dinámico. IMG-01/05 reformulados. AI-04 eliminado. EVT-04 clarificado. Contexto de scripts corregido. Colores del visor actualizados. Campos de lote e indexación sin límite fijo. Nuevos requerimientos: pipeline templates, test de pipeline, entrada PDF, WIA, re-procesado selectivo, estadísticas, folder-watch, notificaciones, versionado de configuración, PDF/A, autocompletado de scripts.

---

## 1. Visión General

Aplicación de escritorio **PySide6** para captura masiva, procesamiento e indexación de documentos. Inspirada en Flexibar.NET pero modernizada con soporte nativo de IA generativa (Claude, OpenAI), scripting Python y una UI moderna.

El sistema es un **framework multi-aplicación**: el usuario define N "aplicaciones" (perfiles de proceso), cada una completamente independiente en su configuración. El launcher muestra la lista de aplicaciones disponibles y el usuario abre la que necesita.

El procesado de cada página se define como un **pipeline dinámico y composable**: una lista ordenada de pasos de tipo imagen, barcode, OCR, IA, script, condición o petición HTTP. No hay pipeline fijo ni separación pre/post barcode.

---

## 2. Módulo 1 — Launcher Principal

| ID | Requerimiento |
|----|---------------|
| LCH-01 | Diálogo principal que lista todas las aplicaciones configuradas (nombre, descripción, fecha creación, fecha modificación, estado activo/inactivo) |
| LCH-02 | Doble-click o botón "Iniciar" para abrir una aplicación en el Workbench |
| LCH-03 | Acceso al **Configurador de Aplicaciones** (ocultable para usuarios no-administrador) |
| LCH-04 | Acceso al **Configurador de Escáner** (TWAIN y WIA) |
| LCH-05 | Acceso a **Opciones globales**: idioma, gestión de usuarios, timeout de sesión, modelos OCR instalados |
| LCH-06 | Editor de **Script Global** (`init_global`): se ejecuta al iniciar el programa, antes de abrir ninguna aplicación |
| LCH-07 | Perfil de usuario: administrador (acceso total) vs usuario básico (solo explotación) |
| LCH-08 | Lanzar directamente una aplicación por línea de comandos: `docscan.exe "Nombre Aplicación"` |
| LCH-09 | Modo directo por línea de comandos (`--direct-mode`): escanea y transfiere sin mostrar interfaz |
| LCH-10 | Indicador de estado de modelos OCR (RapidOCR/EasyOCR): instalado / descargando / no instalado. Descarga en background con barra de progreso; no bloquea el arranque de la aplicación |

---

## 3. Módulo 2 — Gestión de Aplicaciones (Configurador)

Cada "aplicación" es un perfil de proceso almacenado en BD. El configurador permite crear, copiar, modificar, eliminar, importar y exportar aplicaciones como JSON.

| ID | Requerimiento |
|----|---------------|
| CFG-01 | Crear, copiar, renombrar, eliminar y archivar aplicaciones |
| CFG-02 | Exportar aplicación completa (pipeline + scripts + plantillas IA) como JSON |
| CFG-03 | Importar aplicación desde JSON |
| CFG-04 | **Historial de versiones de configuración**: cada guardado genera un snapshot JSON con timestamp y usuario. Listar, comparar y restaurar versiones anteriores. Retención configurable (default: 10 últimas versiones) |

### 3.1 Pestaña General

| ID | Requerimiento |
|----|---------------|
| APP-01 | Nombre, descripción (accesible desde scripts), estado activo/inactivo |
| APP-02 | **Autotransferencia**: transferir automáticamente al finalizar el procesamiento del lote |
| APP-03 | **Cerrar después de transferencia**: volver al launcher tras transferir |
| APP-04 | **Color de fondo personalizado** por aplicación (evitar confusiones entre apps abiertas simultáneamente) |
| APP-05 | Eliminación automática de páginas en blanco (umbral en KB, anverso/reverso/ambos) |
| APP-06 | Formato de imagen de salida: B/N (Group4 TIFF), color (JPEG con calidad configurable, PNG, TIFF, PDF/A-1b, PDF/A-2b) |
| APP-07 | Pestaña por defecto al entrar al Workbench: Lote / Indexación / Verificación |
| APP-08 | Deshabilitar botones de navegación inteligente no necesarios para cada aplicación |

### 3.2 Pestaña Campos de Lote

| ID | Requerimiento |
|----|---------------|
| LOTE-01 | Mostrar diálogo de campos de lote al entrar en la aplicación (configurable) |
| LOTE-02 | Lista de campos configurable sin límite fijo. Tipos por campo: Texto, Fecha, Número, Booleano, Lista desplegable (valores configurables). Campos predefinidos opcionales: Fecha (default hoy), Usuario (default usuario activo) |
| LOTE-03 | Cada campo configurable como: obligatorio, opcional, o calculado (expresión Python sobre otros campos del lote) |
| LOTE-04 | Los campos de lote son accesibles y editables desde la UI durante el proceso y desde los scripts |
| LOTE-05 | Validación de campo: regex opcional con mensaje de error personalizado |

### 3.3 Pestaña de Indexación

| ID | Requerimiento |
|----|---------------|
| IDX-01 | Lista de campos de índice configurable sin límite fijo (a nivel de documento o de página). Tipos: Texto, Fecha, Número, Booleano, Lista |
| IDX-02 | Campo de tipo calculado: expresión Python evaluada sobre campos de lote, barcodes de la página o campos IA |
| IDX-03 | Cada campo configurable como obligatorio u opcional |
| IDX-04 | Validación de campo: regex opcional con mensaje de error personalizado. Se ejecuta en UI (al salir del campo) y antes de la transferencia (bloqueante si el campo es obligatorio) |

### 3.4 Pestaña Pipeline de Procesado

El procesado de cada página es un pipeline único formado por una lista ordenada de pasos. Los pasos se ejecutan en orden; los pasos de tipo `script` y `condition` pueden alterar el flujo de ejecución.

#### Tipos de paso disponibles

| Tipo | Descripción |
|------|-------------|
| `image_op` | Operación de transformación de imagen |
| `barcode` | Lectura de códigos de barras (Motor 1 o Motor 2) |
| `ocr` | Reconocimiento óptico de caracteres |
| `ai` | Extracción de campos / clasificación por IA |
| `script` | Código Python con acceso al contexto completo y control del pipeline |
| `condition` | Expresión Python de una línea; ejecuta una acción si el resultado es `False` |
| `http_request` | Petición HTTP con variables del contexto interpoladas, sin código Python |

#### Requerimientos

| ID | Requerimiento |
|----|---------------|
| IMG-01 | Pipeline único configurable: lista ordenada de pasos de cualquier tipo en cualquier orden. No existe distinción pre/post barcode |
| IMG-02 | El orden de los pasos importa; los pasos se ejecutan secuencialmente salvo que un `script` o `condition` modifique el flujo |
| IMG-03 | Operaciones de imagen disponibles (`image_op`): AutoDeskew, ConvertTo1Bpp, Crop, CropWhiteBorders, CropBlackBorders, Resize, Rotate, RotateAngle, SetBrightness, SetContrast, RemoveLines (H/V/HV), FxDespeckle, FxGrayscale, FxNegative, FxDilate, FxErode, FxEqualizeIntensity, FloodFill, RemoveHolePunch, SetResolution, SwapColor, KeepChannel (R/G/B), RemoveChannel (R/G/B), ScaleChannel |
| IMG-04 | Ventana rectangular de aplicación opcional (píxeles) para operaciones de imagen y lectura de barcode |
| IMG-05 | UI del pipeline: lista de pasos con checkbox (enabled/disabled), tipo, etiqueta, botones editar / eliminar / reordenar. Botón [+ Añadir paso] con selector de tipo |
| IMG-06 | Cada paso se edita en un formulario específico por tipo (diálogo modal) |
| IMG-07 | **Paso `barcode`**: motor (Motor 1: pyzbar / Motor 2: zxing-cpp), simbologías 1D y 2D admitidas, regex de filtro con opción de incluir prefijo de simbología (2 dígitos), orientaciones de búsqueda, umbral de calidad, ventana rectangular. Los resultados se acumulan en `page.barcodes` sin tipología predefinida. La semántica (separador, contenido, etc.) la asigna el `script` o `condition` siguiente si la aplicación lo requiere |
| IMG-08 | **Paso `ocr`**: motor (RapidOCR / EasyOCR / Tesseract), idiomas, página completa o ventana rectangular |
| IMG-09 | **Paso `ai`**: proveedor (Anthropic / OpenAI / local), plantilla de extracción, proveedor de fallback en caso de error o timeout |
| IMG-10 | **Paso `script`**: label descriptivo, nombre del entry point (función Python), editor de código con syntax highlighting y autocompletado del contexto. Recibe `app`, `batch`, `page`, `pipeline` |
| IMG-11 | **Paso `condition`**: expresión Python de una línea evaluada sobre el contexto. Si el resultado es `False`, ejecuta una acción: `skip_step(id)`, `skip_to(id)` o `abort`. No requiere función Python completa |
| IMG-12 | **Paso `http_request`**: método HTTP, URL, cabeceras y cuerpo con variables interpoladas del contexto (`{page.barcodes[0].value}`, `{batch.id}`, `{app.name}`, etc.). Política `on_error`: continuar o abortar |
| IMG-13 | **Plantillas de pipeline**: guardar el pipeline completo de una aplicación como plantilla reutilizable con nombre y descripción. Aplicar una plantilla al crear o editar una aplicación (copia los pasos, no vincula). Exportar/importar plantillas como JSON independiente del export de la aplicación |
| IMG-14 | **Probar pipeline**: botón en la pestaña Pipeline que ejecuta el pipeline completo sobre una imagen de muestra (seleccionable desde fichero o desde un lote existente). Muestra el resultado de cada paso: imagen resultante, barcodes detectados, campos extraídos, errores de script. El resultado no se guarda en ningún lote |
| IMG-15 | Límite configurable de repeticiones para `pipeline.repeat_step()` (default: 3 por paso por página). Si se supera, el pipeline aborta la página y la marca con `needs_review = True` |

### 3.5 Pestaña de Reconocimiento IA / OCR

Esta pestaña configura los proveedores disponibles y las plantillas. La posición del paso IA en el flujo de procesado se define en la pestaña Pipeline.

| ID | Requerimiento |
|----|---------------|
| AI-01 | Configuración de credenciales por proveedor: API key de Anthropic, API key de OpenAI (almacenadas cifradas con Fernet) |
| AI-02 | Proveedor por defecto para los pasos `ai` de esta aplicación: Claude Vision, OpenAI GPT-4o, RapidOCR local, EasyOCR local, Tesseract local |
| AI-03 | Asociación de plantillas de extracción disponibles para esta aplicación |
| AI-04 | Clasificación automática del tipo de documento: el modelo asigna una clase de una lista configurable |
| AI-05 | Visualización de bloques/campos reconocidos sobre el visor (overlays coloreados por tipo de campo) |
| AI-06 | Expresión regular para filtrar qué campos se visualizan en el overlay del visor |

### 3.6 Pestaña de Eventos y Scripts

Entry points de ciclo de vida de la aplicación. Son distintos de los `ScriptStep` del pipeline: se ejecutan en momentos clave del ciclo de vida (inicio, cierre, transferencia, navegación), no durante el procesado de cada imagen.

| ID | Requerimiento |
|----|---------------|
| EVT-01 | **`on_app_start(app, batch)`**: al abrir la aplicación en el Workbench |
| EVT-02 | **`on_app_end(app, batch)`**: al cerrar la aplicación |
| EVT-03 | **`on_import(app, batch)`**: al pulsar Procesar con origen "Importar fichero/PDF". Si está definido, reemplaza la lógica de importación estándar. Con origen Escáner (TWAIN/WIA) este script se ignora |
| EVT-04 | **`on_scan_complete(app, batch)`**: se ejecuta **una sola vez** al terminar el pipeline completo de **todas** las páginas del lote. Para lógica por página, usar un `ScriptStep` al final del pipeline |
| EVT-05 | **`on_transfer_validate(app, batch) -> bool`**: antes de iniciar la transferencia. Retornar `False` cancela la transferencia mostrando un mensaje al usuario |
| EVT-06 | **`on_transfer_advanced(app, batch, result)`**: si está definido, reemplaza la transferencia simple. Acceso completo al lote; puede conectar a cualquier sistema externo |
| EVT-07 | **`on_transfer_page(app, batch, page, result)`**: ejecutado tras copiar cada página en transferencia simple |
| EVT-08 | **`on_navigate_prev(app, batch, page) -> int`** y **`on_navigate_next(app, batch, page) -> int`**: navegación programable; retorna el índice de la página destino |
| EVT-09 | **`on_key_event(app, batch, page, key)`**: combinaciones de teclas (Mayús/Ctrl/Alt + alfanumérica) mapeadas a código Python |
| EVT-10 | Editor Python para cada entry point: syntax highlighting, validación de sintaxis al guardar, log de errores de ejecución en tiempo real, autocompletado de los objetos del contexto |
| EVT-11 | Los scripts de esta pestaña se compilan al abrir la aplicación (mismo mecanismo que los `ScriptStep` del pipeline). Un error de compilación muestra aviso sin impedir abrir la aplicación |

### 3.7 Pestaña de Transferencia Simple

| ID | Requerimiento |
|----|---------------|
| TRS-01 | Activar transferencia por página y/o por documento |
| TRS-02 | Ruta base de transferencia |
| TRS-03 | Subdirectorio destino: ninguno / por fecha / por valor de campo de lote / por valor del primer barcode de la página / **script Python** (`get_subdirectory`) |
| TRS-04 | Nombre de fichero: numerador secuencial / valor del primer barcode de la página / **script Python** (`get_filename`) |
| TRS-05 | Política de colisión de nombres: añadir sufijo / sobrescribir / numerar |
| TRS-06 | Formato de salida: TIFF, JPEG, PDF, PDF/A-1b, PDF/A-2b. En PDF y PDF/A los campos de indexación se embeben como metadatos XMP |
| TRS-07 | Script post-copia por página/documento (`on_transfer_page`): actualizar BD externa, generar CSV, enviar webhook |

### 3.8 Pestaña de Transferencia Avanzada

| ID | Requerimiento |
|----|---------------|
| TRA-01 | Script Python único (`on_transfer_advanced`) con acceso completo al lote (todas las páginas, campos, barcodes, campos IA) |
| TRA-02 | Puede conectar a cualquier sistema: API REST, BD relacional, gestor documental, ERP, SFTP |
| TRA-03 | **Transferencia asíncrona**: guardar lote en estado "Listo para exportar" sin transferir; `DocScanWorker` lo procesa en background |

### 3.9 Pestaña de Modo Lote

| ID | Requerimiento |
|----|---------------|
| MLT-01 | Activar modo lote con ruta de carpeta centralizada compartida en red |
| MLT-02 | Mostrar gestor de lotes automáticamente tras completar la transferencia |
| MLT-03 | **Notificaciones de lote**: al completar un lote procesado por `DocScanWorker`, enviar: webhook POST (cuerpo JSON configurable con variables del lote) y/o email (SMTP configurable, asunto y cuerpo con plantilla) |

---

## 4. Módulo 3 — Interfaz de Explotación (Workbench)

### Layout principal

```
┌─────────────┬──────────────────────────────┬─────────────────┐
│  Miniaturas │     Visor de documento        │  Barcode viewer │
│  de páginas │     Borde coloreado:          │  Contadores     │
│  (scroll)   │   🟠 barcode rol separador   │                 │
│             │   🟢 barcode sin rol sep     │  ─────────────  │
│             │   🔵 campos IA extraídos     │  Pestañas:      │
│             │   🔴 needs_review            │  - Lote         │
│             │   ⚪ sin reconocimiento      │  - Indexación   │
│             │   (overlay semitransparente)  │  - Verificación │
├─────────────┼──────────────────────────────┤                 │
│  Botones    │  Origen: Escáner / Importar  │                 │
│  acción     │  Config predefinida + Scan   │                 │
└─────────────┴──────────────────────────────┴─────────────────┘
```

| ID | Requerimiento |
|----|---------------|
| UI-01 | Zona de miniaturas: scrollable, doble-click para navegar, borde coloreado según estado de la página |
| UI-02 | Visor principal: zoom rueda, arrastre, zoom rectángulo, lupa, ajustar a página; menú contextual |
| UI-03 | Borde del visor coloreado según estado de la página (prioridad descendente): 🔴 rojo (`flags.needs_review`), 🟠 naranja (tiene barcode con `role='separator'`), 🔵 azul (tiene campos IA extraídos), 🟢 verde (tiene barcodes sin rol asignado), ⚪ gris (sin reconocimiento). Los roles de barcode son opcionales y los asigna el script; si ninguna aplicación los usa, el visor muestra verde/gris simplemente |
| UI-04 | Overlay semitransparente sobre cada barcode detectado y cada campo IA reconocido, coloreado por tipo de campo |
| UI-05 | Botón Procesar; acceso rápido a la configuración por defecto del escáner |
| UI-06 | Botón Transferencia: ejecuta `on_transfer_validate` → diálogo de confirmación → transferencia → log de resultado |
| UI-07 | Botones de manipulación: marcar/desmarcar página (ignorar en transferencia), borrar desde página actual, insertar barcode manual, eliminar barcode manual, rotar 90° |
| UI-08 | Panel de barcodes: lista todos los barcodes de la página actual (valor, simbología, motor, rol si está asignado), copiable al portapapeles, contadores totales del lote |
| UI-09 | Navegación: primera/anterior/siguiente/última + inteligente: por páginas con barcode, por páginas con `needs_review`, por páginas sin reconocimiento, programable (`on_navigate_prev/next`) |
| UI-10 | Procesado multihilo: hebra de carga y hebra de reconocimiento en paralelo. La UI nunca se bloquea. Barra de progreso por página |
| UI-11 | Ctrl+P: re-evaluar el pipeline completo de la página actual |
| UI-12 | Atajos de teclado configurables por aplicación (`on_key_event`) |
| UI-13 | Orígenes de entrada: Escáner (TWAIN o WIA, seleccionable por aplicación), Importar imágenes (TIFF/JPEG/PNG/BMP — fichero individual o carpeta completa), Importar PDF (cada página extraída como imagen con DPI configurable, default 300dpi) |

---

## 5. Módulo 4 — Gestión de Lotes

| ID | Requerimiento |
|----|---------------|
| BAT-01 | Estados: Creado → Leído → Verificado → Listo para exportar → Exportado (+ Error Lectura, Error Exportación) |
| BAT-02 | Cada lote es una carpeta: `{hostname}_{YYYYMMDD_HHMMSS}/` con imágenes + `batch_state.json` (estado, campos de lote, páginas con sus resultados, estadísticas) |
| BAT-03 | Archivo `batch.lock` para prevenir acceso concurrente. El modo Supervisor puede forzar la liberación si el proceso propietario no responde |
| BAT-04 | Interfaz de gestión: lista con filtro por estado, fecha, aplicación, estación de trabajo |
| BAT-05 | Modo Usuario (operaciones básicas) y Supervisor (contraseña): el supervisor puede liberar locks, cambiar estados manualmente y eliminar lotes |
| BAT-06 | Historial inmutable de operaciones: cada cambio de estado, error y transferencia se registra con timestamp y usuario |
| BAT-07 | Refresco periódico del gestor (default 20s, configurable) |
| BAT-08 | **`DocScanWorker`**: proceso CLI desatendido que consume lotes en estado "Leído" o "Listo para exportar". Ejecuta el pipeline completo con el mismo motor que la UI |
| BAT-09 | **Estadísticas por lote**: almacenadas en `batch_state.json` al finalizar el pipeline. Incluyen: total páginas, páginas con barcode, páginas con campos IA, páginas `needs_review`, duración total, tiempo medio por página, duración acumulada por tipo de paso. Visibles en el panel de detalle del gestor de lotes |
| BAT-10 | **Re-procesado selectivo**: desde el Workbench, menú contextual sobre página(s) → "Re-procesar desde paso..." (selector del paso del pipeline). Desde el gestor: "Re-procesar páginas con error" ejecuta el pipeline solo sobre las páginas con `needs_review = True` |
| BAT-11 | **Folder-watch en `DocScanWorker`**: monitorizar una carpeta de entrada; al detectar ficheros nuevos (imágenes o PDFs), crear y procesar un lote automáticamente. Trigger configurable: por fichero individual, por lote (timeout de inactividad) o por fichero centinela |

---

## 6. Módulo 5 — Diseñador de Plantillas IA

| ID | Requerimiento |
|----|---------------|
| TPL-01 | Gestor de plantillas: nombre, descripción, proveedor objetivo |
| TPL-02 | Editor de prompt con variables interpolables del contexto: `{page.barcodes[0].value}`, `{batch.fields['campo']}`, y cualquier expresión evaluable |
| TPL-03 | Campos por plantilla: nombre, tipo (Texto/Fecha/Número/Booleano), obligatorio, descripción para el modelo |
| TPL-04 | Test de plantilla: seleccionar imagen de muestra, ejecutar extracción, mostrar campos extraídos y confianza por campo |
| TPL-05 | Exportar/importar plantillas como JSON |

---

## 7. Sistema de Scripts Python

### Contexto disponible en todos los scripts

```python
app      # AppContext: nombre, descripción, config, propiedades custom
batch    # BatchContext: campos de lote, lista de páginas, estado
page     # PageContext: índice, imagen_b64, page.barcodes, page.ocr_text,
         #   page.ai_fields, page.flags (needs_review, review_reason,
         #   script_errors, processing_errors)
pages    # list[PageContext]: todas las páginas del lote
fields   # dict: alias de page.fields (campos de indexación de la página actual)
result   # ExportResult: disponible en scripts de transferencia
log      # Logger: log.info(), log.warning(), log.error()
http     # httpx.Client preconfigurado para APIs externas
```

`page.barcodes` es una lista plana de `Barcode` con: `value`, `symbology`, `engine`, `step_id`, `position`, `role` (asignable por el script).

Módulos disponibles sin importar: `re`, `json`, `datetime`, `Path`.

### Control de flujo desde `ScriptStep` (objeto `pipeline`)

```python
pipeline.skip_step(step_id)          # Salta un paso específico
pipeline.skip_to(step_id)            # Salta hasta un paso (inclusive)
pipeline.abort(reason="")            # Detiene el pipeline; marca needs_review
pipeline.repeat_step(step_id)        # Re-ejecuta un paso (máx. configurable, default 3)
pipeline.replace_image(np.ndarray)   # Sustituye la imagen en curso
pipeline.get_step_result(step_id)    # Resultado de un paso ya ejecutado
pipeline.set_metadata(key, value)    # Almacena datos entre pasos
pipeline.get_metadata(key)           # Recupera datos almacenados
```

### Entry points de ciclo de vida (pestaña Eventos)

| Función | Cuándo | Retorno |
|---------|--------|---------|
| `init_global(app)` | Al iniciar DocScan Studio | — |
| `on_app_start(app, batch)` | Al abrir la aplicación en el Workbench | — |
| `on_app_end(app, batch)` | Al cerrar la aplicación | — |
| `on_import(app, batch)` | Al importar fichero/PDF (no con escáner) | — |
| `on_scan_complete(app, batch)` | Al terminar el pipeline de todas las páginas del lote | — |
| `on_transfer_validate(app, batch) -> bool` | Antes de transferir; `False` cancela | `bool` |
| `on_transfer_advanced(app, batch, result)` | Transferencia avanzada (reemplaza la simple) | — |
| `on_transfer_page(app, batch, page, result)` | Post-copia por página en transferencia simple | — |
| `on_navigate_prev(app, batch, page) -> int` | Navegación anterior programable | `int` |
| `on_navigate_next(app, batch, page) -> int` | Navegación siguiente programable | `int` |
| `on_key_event(app, batch, page, key)` | Tecla personalizada | — |
| `get_subdirectory(app, batch, page) -> str` | Subdirectorio de transferencia simple | `str` |
| `get_filename(app, batch, page) -> str` | Nombre de fichero en transferencia simple | `str` |

---

## 8. Arquitectura Recomendada

```
docscan/
├── main.py
├── app/
│   ├── ui/
│   │   ├── launcher/
│   │   ├── workbench/
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
│   │   │   │   ├── tab_pipeline.py        # Editor de lista de pasos + botón Probar
│   │   │   │   ├── tab_ai_ocr.py
│   │   │   │   ├── tab_events.py          # Entry points de ciclo de vida
│   │   │   │   ├── tab_transfer.py
│   │   │   │   └── tab_batch_mode.py
│   │   │   ├── step_dialogs/              # Un diálogo por tipo de paso
│   │   │   │   ├── image_op_dialog.py
│   │   │   │   ├── barcode_step_dialog.py
│   │   │   │   ├── ocr_step_dialog.py
│   │   │   │   ├── ai_step_dialog.py
│   │   │   │   ├── script_step_dialog.py
│   │   │   │   ├── condition_step_dialog.py
│   │   │   │   └── http_request_step_dialog.py
│   │   │   └── script_editor.py           # Widget editor Python reutilizable
│   │   ├── batch_manager/
│   │   └── template_designer/
│   ├── pipeline/
│   │   ├── steps.py                       # Dataclasses de todos los tipos de paso
│   │   ├── context.py                     # PipelineContext (control de flujo)
│   │   ├── executor.py                    # PipelineExecutor
│   │   └── serializer.py                  # JSON ↔ list[PipelineStep]
│   ├── services/
│   │   ├── scanner_service.py             # BaseScanner + TwainScanner + WiaScanner
│   │   ├── import_service.py              # Importar imágenes y PDFs (pymupdf)
│   │   ├── barcode_service.py             # Motor 1 (pyzbar) + Motor 2 (zxing-cpp)
│   │   ├── image_pipeline.py              # Implementación de todas las ImageOp
│   │   ├── ai_service.py
│   │   ├── ocr_service.py
│   │   ├── script_engine.py
│   │   ├── transfer_service.py
│   │   ├── batch_service.py
│   │   └── notification_service.py        # Webhooks + email SMTP
│   ├── providers/
│   │   ├── base_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   └── local_ocr_provider.py          # RapidOCR / EasyOCR / Tesseract
│   ├── models/
│   │   ├── application.py
│   │   ├── batch.py
│   │   ├── page.py
│   │   ├── barcode.py
│   │   └── template.py
│   ├── workers/
│   │   ├── scan_worker.py
│   │   ├── recognition_worker.py          # Usa PipelineExecutor por página
│   │   └── transfer_worker.py
│   └── db/
│       ├── database.py                    # SQLite en WAL mode
│       ├── repositories/
│       └── migrations/
├── config/
│   ├── settings.py
│   └── secrets.py
├── docscan_worker/
│   ├── worker_main.py
│   └── folder_watcher.py                  # Folder-watch con watchdog
├── tests/
└── resources/
    ├── styles/
    └── icons/
```

---

## 9. Stack Tecnológico

| Categoría | Tecnología | Notas |
|-----------|------------|-------|
| UI | PySide6 | |
| ORM / BD | SQLAlchemy 2.x + SQLite | **WAL mode obligatorio** |
| Barcode Motor 1 | `pyzbar` + `opencv-python` | Rápido, amplio soporte 1D |
| Barcode Motor 2 | `zxing-cpp` | Más rápido en múltiples códigos, mejor 2D |
| Pipeline imagen | `opencv-python` + `Pillow` | |
| OCR principal | `rapidocr-onnxruntime` | Sin PyTorch, modelos ~10MB, descarga rápida |
| OCR alternativo | `easyocr` | Mayor precisión, modelos ~500MB, requiere PyTorch |
| OCR fallback | `pytesseract` | |
| IA — Anthropic | `anthropic` SDK | Claude Vision |
| IA — OpenAI | `openai` SDK | GPT-4o Vision |
| Escáner TWAIN | `pytwain` | Windows; requiere TWAIN DSM 64-bit si Python es 64-bit |
| Escáner WIA | `pywin32` (`win32com`) | Windows; alternativa sin problemas 64-bit |
| PDF entrada/salida | `pymupdf` (fitz) | Lectura, generación, PDF/A |
| Exportación datos | `openpyxl`, `csv` stdlib | |
| HTTP | `httpx` | Steps http_request, webhooks, llamadas IA |
| Email | `smtplib` stdlib | Notificaciones de lote |
| Folder-watch | `watchdog` | Monitorización de carpetas en DocScanWorker |
| Cifrado | `cryptography` (Fernet) | API keys y secrets |
| Configuración | `pydantic-settings` | |
| Scheduler | `APScheduler` | Procesado periódico en DocScanWorker |
| Editor scripts | `QScintilla` | Syntax highlighting + stubs de autocompletado |
| Testing | `pytest`, `pytest-qt` | |
| Python | 3.14 (Xubuntu: invocar como `python3.14`) | |

---

## 10. Criterios de Aceptación Clave

- El procesado (pipeline completo) es **no bloqueante**: siempre en `QThread`; la UI nunca se congela
- Las API keys nunca se almacenan en texto plano; siempre cifradas con Fernet
- La aplicación funciona **offline** para barcode + OCR local (RapidOCR/Tesseract)
- Los scripts pueden modificarse y recompilarse sin reiniciar la aplicación
- Un error en un `ScriptStep` no detiene el pipeline ni crashea la app; se registra en `page.flags.script_errors`
- El configurador es ocultable al usuario final (perfil básico)
- El sistema de lotes es resistente a interrupciones: el estado siempre es consistente; un reinicio puede retomar el lote
- SQLite en **WAL mode** para concurrencia entre la UI y el `DocScanWorker`
- `pipeline.repeat_step()` tiene un límite máximo de repeticiones para prevenir bucles infinitos
- Los modelos OCR se descargan en background con indicador de progreso; no bloquean el arranque
- El historial de versiones de configuración permite restaurar cualquier snapshot anterior
