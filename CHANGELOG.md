# 📋 Changelog

Todos los cambios relevantes de DocScan Studio están documentados en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [0.1.0] — 2026-03-26

### 🚀 Distribución e instaladores
- **UI de actualización**: diálogo de descarga con barra de progreso, notas de release y verificación SHA-256
- **Banner de actualización**: notificación no invasiva en el Launcher con botones "Ver novedades", "Actualizar" e "Ignorar"
- **Botón "Buscar actualizaciones"** en el diálogo Acerca de
- **Auto-check al inicio**: comprobación de nuevas versiones en segundo plano tras arrancar
- **PyInstaller specs**: configuración de empaquetado para Linux y Windows
- **AppImage**: recipe AppImageBuilder + fichero .desktop para distribución Linux
- **Inno Setup**: script de instalador Windows con español/inglés/catalán y modo silencioso
- **CI/CD**: GitHub Actions workflow para build automático y release al crear tags `v*`
- **Informe de licenciamiento**: análisis de licencias, modelos de negocio, plataformas de venta y protección de código

### 🏗️ Infraestructura
- Rama `production` para releases estables
- Versión centralizada en `app/_version.py`
- Auto-update service con GitHub Releases API + SHA-256
- Estilos QSS para banner de actualización (tema claro y oscuro)
- 21 tests nuevos para UI de actualización (849 total)

---

## [0.1 RC] — 2026-03-26

### 📖 Documentación
- README.md completo con badges, screenshots, arquitectura, pipeline, scripting, AI Mode y roadmap
- Manual de usuario Word (.docx) con 12 capítulos y 18 figuras reales
- Documentación web MkDocs Material con 13 páginas, publicada en GitHub Pages
- 73 tooltips añadidos a 14 ficheros UI (batch manager, configurador, workbench)
- Diálogo "Acerca de" con versión, logo, stack tecnológico y copyright
- Generador de documentos clínicos de ejemplo para demos
- Auditoría de seguridad: sin API keys ni credenciales expuestas
- `.gitignore` reforzado con exclusiones de seguridad

---

## [Release 3] — 2026-03-25

### ✨ Funcionalidades
- **AI MODE**: asistente conversacional integrado en el Launcher para crear y configurar aplicaciones mediante lenguaje natural (Anthropic / OpenAI)
- **Pipeline Assistant**: asistente IA contextual por aplicación en el configurador
- **Test Pipeline** (IMG-14): ejecución del pipeline sobre imagen de muestra con resultados paso a paso
- **Export/Import** (CFG-02/03): exportar e importar aplicaciones como ficheros `.docscan` (JSON)
- **Sidebar colapsable**: panel lateral con 10 iconos vectoriales QPainter, animación de 150ms
- **Política de colisión** (TRS-05): sufijo numérico, sobreescribir o fusionar multi-página PDF/TIFF
- **Detección de páginas en blanco** (APP-05): análisis por histograma con auto-exclusión configurable
- **Splash screen**: pantalla de carga con logo, versión y progreso de inicialización

### 🚫 Descartados
- ConditionStep / HttpRequestStep — redundantes con ScriptStep + AI MODE
- Perfiles de usuario (LCH-07/BAT-05) — innecesario para mono-estación
- batch.lock (BAT-03) — foco mono-estación
- Pipeline templates (IMG-13) — cubierto por AI MODE + Export/Import

---

## [Release 2b] — 2026-03-22

### ✨ Funcionalidades
- **Panel de verificación personalizado**: widget QWidget definido por script en `verification_panel`, insertado como pestaña en el Workbench

---

## [Release 2] — 2026-03-21

### ✨ Funcionalidades
- **Internacionalización** (i18n): soporte multilenguaje para Español, English y Català con `QT_TRANSLATE_NOOP` y funciones lazy
- **Atajos de teclado**: 17 shortcuts para el Workbench (navegación, zoom, rotación, marcado, eliminación)
- **OCR estructurado**: resultados con regiones word-level y coordenadas
- **Field overlays**: visualización de regiones OCR sobre el visor de documentos
- **Compatibilidad Windows**: soporte TWAIN + WIA para escáneres, ajustes cross-platform
- **Icono de aplicación**: en títulos de ventana y barra de tareas Windows

---

## [Release 1B] — 2026-03-20

### ✨ Funcionalidades
- **ImageLib**: librería de operaciones de imagen (load, save, merge, split, DPI, color)
- **ImageConfig**: dataclass de configuración de imagen con parse/serialize
- **Pestaña Imagen**: nueva pestaña en el configurador (formato, color, compresión)
- **Mejoras de transferencia**: conversión de formato, DPI y color al exportar

### 🔧 Cambios técnicos
- Eliminación de AiStep del pipeline (absorbido por ScriptStep)
- Unificación `ai_fields` → `custom_fields` → `page.fields`
- Fix memory leak: `WA_DeleteOnClose` + `deleteLater` en ventanas secundarias
- Guard para señales tardías post-cierre de ventana
- Resume automático de pipeline al reabrir lote
- 4 migraciones Alembic aplicadas
- `requirements-dev.txt` con dependencias de desarrollo separadas

### 🐛 Correcciones
- Navegación next-barcode / next-review
- Parsing de `events_json` para string y dict
- Tamaños de ventana ampliados (configurador 950×700, workbench 1440×900)

---

## [Release 1] — 2026-03-19

### ✨ Funcionalidades

#### Infraestructura (pasos 1-5)
- Pipeline engine: steps.py, context.py, executor.py, serializer.py
- PipelineContext con control de flujo: skip_step, skip_to, abort, repeat_step
- Settings con pydantic-settings + Secrets con Fernet
- Base de datos SQLite con WAL mode obligatorio + repositorios

#### Servicios (pasos 6-11)
- **ScriptEngine**: compilación de scripts al cargar app, ejecución con timeout
- **BarcodeService**: Motor 1 (pyzbar, 12 simbologías) + Motor 2 (zxing-cpp, 14 simbologías)
- **ImagePipeline**: 23+ operaciones de imagen (deskew, crop, filtros, morfología...)
- **OcrService**: RapidOCR (primary), EasyOCR (alternative), Tesseract (fallback)
- **Proveedores IA**: Anthropic (Claude) + OpenAI (GPT-4o) con Strategy pattern
- **PipelineExecutor**: ejecución stateless con max repeat limit

#### Soporte (pasos 12-15)
- **ScannerService**: SANE (Linux) con subprocess para thread-safety
- **ImportService**: TIFF multi-página, JPEG, PNG, BMP, PDF (rasterizado con PyMuPDF)
- **BatchService**: gestión de lotes con estados y auditoría
- **TransferService**: transferencia simple a carpeta + avanzada por script
- **NotificationService**: email + webhook

#### Launcher (paso 16)
- Ventana principal con lista de aplicaciones
- Crear, editar, duplicar, eliminar aplicaciones
- Búsqueda de aplicaciones

#### Configurador (pasos 17-18)
- 6 pestañas: General, Imagen, Campos de Lote, Pipeline, Eventos, Transferencia
- Editor visual de pipeline con drag & drop
- Diálogos de edición por tipo de paso (ImageOp, Barcode, OCR, Script)
- Editor de eventos del ciclo de vida con integración VS Code

#### Workbench (paso 19)
- Panel de miniaturas con estados de color
- Visor de documentos con zoom, pan y overlays
- Panel de barcodes con tabla y contadores
- Panel de metadatos con campos dinámicos
- Panel de log en tiempo real
- Workers QThread: scan, recognition, transfer
- Drag & drop para importación

#### Batch Manager (paso 20)
- Histórico de lotes con filtros (aplicación, estación, fecha)
- Panel de detalle con estadísticas, páginas e historial
- Reabrir lotes anteriores en el Workbench
- Auto-refresco cada 20 segundos

#### Worker (paso 21)
- DocScanWorker CLI para procesamiento desatendido
- Folder watcher con watchdog

#### Tests (paso 22)
- Suite de tests con pytest + pytest-qt
- Tests de repositorios, servicios, pipeline, UI y integración

---

## Métricas del proyecto

| Métrica | Valor |
|---------|-------|
| Líneas de código (app) | 19.776 |
| Líneas de test | 11.618 |
| Ficheros fuente | 94 |
| Tests | 813 passing ✅ |
| Operaciones de imagen | 23 |
| Simbologías barcode | 14 |
| Motores OCR | 3 |
| Idiomas de interfaz | 3 |
