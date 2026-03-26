<p align="center">
  <img src="resources/icons/docscan.svg" alt="DocScan Studio" width="120" height="120">
</p>

<h1 align="center">📄 DocScan Studio</h1>

<p align="center">
  <strong>Plataforma de captura, procesamiento e indexación de documentos con IA generativa</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1_RC-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.10-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/tests-813_passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/license-proprietary-red?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Linux_%7C_Windows-lightgrey?style=flat-square" alt="Platform">
</p>

<p align="center">
  <a href="#-características">Características</a> •
  <a href="#-inicio-rápido">Inicio rápido</a> •
  <a href="#-arquitectura">Arquitectura</a> •
  <a href="#-pipeline">Pipeline</a> •
  <a href="#-scripting">Scripting</a> •
  <a href="#-ai-mode">AI Mode</a> •
  <a href="#-stack-tecnológico">Stack</a>
</p>

---

## 🎯 ¿Qué es DocScan Studio?

DocScan Studio es una aplicación de escritorio **multi-aplicación** para la captura por lotes, procesamiento e indexación de documentos. Cada "aplicación" es un perfil de procesamiento completamente independiente con su propio pipeline, scripts, campos y configuración de transferencia.

> **Inspirado en Flexibar.NET** — reimaginado desde cero con Python, IA generativa y un pipeline completamente composable.

### Flujo de trabajo típico

```
📥 Escanear/Importar → 🔄 Pipeline (imagen + barcode + OCR + scripts) → ✅ Verificar → 📤 Transferir
```

---

## ✨ Características

<table>
<tr>
<td width="50%">

### 🖨️ Captura
- Escaneo directo via **SANE** (Linux) y **TWAIN/WIA** (Windows)
- Importación por arrastrar y soltar (TIFF, JPEG, PNG, PDF, BMP)
- Alimentador automático (ADF) con multi-página
- Detección automática de páginas en blanco

</td>
<td width="50%">

### 🔄 Pipeline composable
- 4 tipos de paso: imagen, barcode, OCR, script
- Orden libre y configurable por aplicación
- 23+ operaciones de imagen (deskew, crop, filtros...)
- Asistente IA para construir pipelines

</td>
</tr>
<tr>
<td>

### 🔍 Reconocimiento
- **Barcodes**: pyzbar + zxing-cpp (14 simbologías)
- **OCR**: RapidOCR, EasyOCR, Tesseract
- **IA**: Claude (Anthropic) y GPT-4o (OpenAI)
- Regiones configurables por coordenadas

</td>
<td>

### 📊 Indexación
- Campos de lote (texto, fecha, número, booleano, desplegable)
- Campos de documento/página con expresiones calculadas
- Separación automática por código de barras
- Panel de verificación personalizable por script

</td>
</tr>
<tr>
<td>

### 🤖 AI Mode
- Asistente conversacional integrado en el Launcher
- Crea/modifica aplicaciones por lenguaje natural
- Pipeline Assistant para cada configuración
- Test pipeline sobre imagen de muestra

</td>
<td>

### 📤 Transferencia
- Exportación a carpeta (TIFF, JPEG, PNG, PDF, PDF/A, BMP)
- Transferencia avanzada por script Python
- Políticas de colisión: sufijo, sobreescribir, fusionar
- Fusión multi-página PDF/TIFF

</td>
</tr>
<tr>
<td>

### 🐍 Scripting Python
- Motor de scripts con contexto completo
- 7+ eventos del ciclo de vida
- Acceso a `app`, `batch`, `page`, `pipeline`
- Timeout configurable, errores no bloquean

</td>
<td>

### 🌐 Multi-idioma & Temas
- Español, English, Català
- Tema claro y oscuro
- Sidebar colapsable con iconos vectoriales
- Atajos de teclado configurables (17+)

</td>
</tr>
</table>

---

## 🚀 Inicio rápido

### Requisitos previos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | **3.14+** | En Linux: `python3.14` |
| SQLite | 3.35+ | Incluido con Python |
| SANE | - | Solo Linux, para escaneo |
| Tesseract | 5.x | Opcional, OCR fallback |

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/ferreret/docscan.git
cd docscan

# 2. Crear entorno virtual
python3.14 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Inicializar base de datos
alembic upgrade head

# 5. ¡Lanzar!
python3.14 main.py
```

### Modos de ejecución

```bash
# 🏠 Launcher — gestionar aplicaciones
python3.14 main.py

# 🔧 Abrir directamente una aplicación
python3.14 main.py "Facturas Proveedores"

# 🤖 Modo headless — escanear y transferir sin UI
python3.14 main.py --direct-mode "Facturas Proveedores"

# ⚙️ Worker desatendido — procesar desde carpeta
python3.14 -m docscan_worker --batch-path /ruta/a/documentos
```

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        DocScan Studio                           │
├─────────────┬──────────────┬──────────────┬─────────────────────┤
│  🏠 Launcher │ ⚙️ Configurador│ 📋 Workbench │ 📂 Batch Manager  │
├─────────────┴──────────────┴──────────────┴─────────────────────┤
│                        Servicios                                │
│  ScriptEngine │ BarcodeService │ ImagePipeline │ OcrService     │
│  TransferSvc  │ BatchService   │ ImportService │ ScannerService │
├─────────────────────────────────────────────────────────────────┤
│                     Pipeline Executor                           │
│         PipelineStep → Context → Flow Control → Results         │
├─────────────────────────────────────────────────────────────────┤
│                      Proveedores IA                             │
│              Anthropic │ OpenAI │ Local OCR                     │
├─────────────────────────────────────────────────────────────────┤
│                     Persistencia                                │
│           SQLAlchemy 2.x │ SQLite WAL │ Alembic                │
└─────────────────────────────────────────────────────────────────┘
```

### Estructura del proyecto

```
docscan/
├── app/
│   ├── db/              # Database, repositorios, modelos ORM
│   ├── models/          # Dataclasses y enums de dominio
│   ├── pipeline/        # Steps, Context, Executor, Serializer
│   ├── providers/       # Anthropic, OpenAI, LocalOCR (Strategy)
│   ├── services/        # Lógica de negocio (barcode, OCR, imagen, transfer...)
│   ├── ui/
│   │   ├── launcher/    # Ventana principal, sidebar, AI Mode
│   │   ├── configurator/# 6 pestañas + diálogos de pasos
│   │   ├── workbench/   # Visor, miniaturas, paneles
│   │   └── batch_manager/# Historial de lotes
│   └── workers/         # QThread: scan, recognition, transfer
├── config/              # Settings (pydantic) + Secrets (Fernet)
├── resources/
│   ├── icons/           # SVG vectoriales
│   ├── styles/          # QSS temas claro/oscuro
│   └── translations/    # .ts para ES, EN, CAT
├── alembic/             # Migraciones de BD
├── tests/               # 813 tests (pytest + pytest-qt)
└── docs/                # Documentación e informes
```

### Métricas del código

| Métrica | Valor |
|---------|-------|
| Líneas de código (app) | **19.776** |
| Líneas de test | **11.618** |
| Ficheros fuente | **94** |
| Ficheros de test | **32** |
| Tests pasando | **813** ✅ |
| Ratio código:test | **1.7:1** |

---

## 🔄 Pipeline

El pipeline es el **corazón de DocScan Studio**. Cada página escaneada/importada atraviesa una secuencia configurable de pasos:

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ ImageOp  │──▶│ Barcode  │──▶│   OCR    │──▶│  Script  │
│ AutoDesk │   │ Motor 1+2│   │ RapidOCR │   │ Separar  │
│ Crop     │   │ QR+C128  │   │          │   │ por BC   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### Tipos de paso

| Tipo | Icono | Descripción |
|------|-------|-------------|
| `image_op` | 🖼️ | Operaciones sobre la imagen (23 disponibles) |
| `barcode` | 📊 | Lectura de códigos de barras (2 motores, 14 simbologías) |
| `ocr` | 📝 | Reconocimiento óptico de caracteres (3 motores) |
| `script` | 🐍 | Script Python con acceso al contexto completo |

### Operaciones de imagen disponibles

<details>
<summary>📋 Ver las 23 operaciones</summary>

| Operación | Descripción |
|-----------|-------------|
| `AutoDeskew` | Corrección automática de inclinación |
| `ConvertTo1Bpp` | Conversión a blanco y negro (1 bit) |
| `Crop` | Recorte rectangular |
| `CropWhiteBorders` | Recorte automático de márgenes blancos |
| `CropBlackBorders` | Recorte automático de márgenes negros |
| `Resize` | Redimensionar |
| `Rotate` | Rotar 90°, 180°, 270° |
| `RotateAngle` | Rotación libre por ángulo |
| `SetBrightness` | Ajustar brillo (-100 a +100) |
| `SetContrast` | Ajustar contraste (-100 a +100) |
| `RemoveLines` | Eliminar líneas horizontales/verticales |
| `FxDespeckle` | Eliminar ruido (speckle) |
| `FxGrayscale` | Convertir a escala de grises |
| `FxNegative` | Invertir colores |
| `FxDilate` | Dilatación morfológica |
| `FxErode` | Erosión morfológica |
| `FxEqualizeIntensity` | Ecualización de histograma |
| `FloodFill` | Relleno por inundación |
| `RemoveHolePunch` | Eliminar agujeros de perforadora |
| `SetResolution` | Ajustar DPI |
| `SwapColor` | Intercambiar colores |
| `KeepChannel` | Extraer canal de color (R/G/B) |
| `RemoveChannel` | Eliminar canal de color |

</details>

### Simbologías de barcode soportadas

<details>
<summary>📊 Ver simbologías</summary>

| Simbología | Motor 1 (pyzbar) | Motor 2 (zxing-cpp) |
|------------|:-:|:-:|
| Code128 | ✅ | ✅ |
| Code39 | ✅ | ✅ |
| Code93 | ✅ | ✅ |
| Codabar | ✅ | ✅ |
| EAN-13 | ✅ | ✅ |
| EAN-8 | ✅ | ✅ |
| UPC-A | ✅ | ✅ |
| UPC-E | ✅ | ✅ |
| ITF | ✅ | ✅ |
| QR Code | ✅ | ✅ |
| PDF417 | ✅ | ✅ |
| DataMatrix | ✅ | ✅ |
| Aztec | ❌ | ✅ |
| MaxiCode | ❌ | ✅ |
| MicroQR | ❌ | ✅ |

</details>

### Control de flujo en scripts

El `PipelineContext` permite que los scripts controlen la ejecución:

```python
def mi_script(app, batch, page, pipeline):
    # Saltar un paso
    pipeline.skip_step("paso_ocr_1")

    # Saltar hasta un paso específico
    pipeline.skip_to("paso_final")

    # Repetir el paso actual (máx. 3 veces)
    if not page.barcodes:
        pipeline.repeat_step("paso_barcode_1")

    # Reemplazar la imagen procesada
    import cv2
    gray = cv2.cvtColor(pipeline.current_image, cv2.COLOR_BGR2GRAY)
    pipeline.replace_image(gray)

    # Abortar el pipeline (marca la página para revisión)
    if page.flags.get("critical_error"):
        pipeline.abort("Error crítico detectado")

    # Compartir datos entre pasos
    pipeline.set_metadata("doc_type", "factura")
    doc_type = pipeline.get_metadata("doc_type")
```

---

## 🐍 Scripting

Todos los scripts reciben un contexto completo para interactuar con la aplicación:

### Objetos disponibles

| Objeto | Descripción | Disponible en |
|--------|-------------|---------------|
| `app` | Configuración de la aplicación | Todos |
| `batch` | Datos del lote actual | Todos |
| `page` | Página actual (imagen, barcodes, OCR, campos) | Todos |
| `pipeline` | Control de flujo del pipeline | Solo en `ScriptStep` |
| `log` | Logger del script | Todos |
| `http` | Cliente httpx para peticiones HTTP | Todos |
| `re`, `json`, `datetime`, `Path` | Módulos estándar | Todos |

### Eventos del ciclo de vida

```python
# on_scan_complete — después de que el pipeline procese todas las páginas
def on_scan_complete(app, batch, page):
    log.info(f"Lote {batch.name} procesado: {len(batch.pages)} páginas")
    if any(p.flags.get("needs_review") for p in batch.pages):
        log.warning("Hay páginas pendientes de revisión")

# on_transfer_validate — validar antes de transferir
def on_transfer_validate(app, batch, page):
    if not batch.fields.get("numero_factura"):
        raise ValueError("El número de factura es obligatorio")

# on_transfer_page — personalizar la transferencia por página
def on_transfer_page(app, batch, page):
    barcode = page.barcodes[0].data if page.barcodes else "SIN_BC"
    page.fields["subdirectory"] = f"facturas/{barcode[:4]}"
```

### Ejemplo: separación de documentos por barcode

```python
def separar_documentos(app, batch, page, pipeline):
    """Cada vez que aparece un barcode Code128, inicia un nuevo documento."""
    separadores = [b for b in page.barcodes if b.symbology == "CODE128"]

    if separadores:
        # Marcar como página separadora
        page.fields["es_separador"] = True
        page.fields["id_documento"] = separadores[0].data
        log.info(f"Nuevo documento: {separadores[0].data}")
    else:
        # Heredar ID del documento anterior
        prev_id = pipeline.get_metadata("ultimo_doc_id")
        page.fields["id_documento"] = prev_id or "DOC_DEFAULT"

    # Guardar para la siguiente página
    if page.barcodes:
        pipeline.set_metadata("ultimo_doc_id", page.barcodes[0].data)
```

---

## 🤖 AI Mode

El **AI Mode** es un asistente conversacional integrado que permite crear y configurar aplicaciones mediante lenguaje natural.

### Capacidades

- 🗣️ **Crear aplicaciones** describiendo el caso de uso
- 🔧 **Modificar configuración** sin navegar por pestañas
- 🔄 **Generar pipelines** a partir de la descripción del documento
- 📝 **Escribir scripts** para lógica personalizada
- 🧪 **Probar pipeline** sobre una imagen de muestra

### Ejemplo de conversación

```
👤 Necesito una aplicación para digitalizar albaranes. Cada albarán tiene
   un barcode Code128 en la esquina superior derecha con el número de pedido.

🤖 He creado la aplicación "Albaranes" con:
   - Pipeline: AutoDeskew → Crop región barcode → Barcode Motor 2 → Script separador
   - Campo de lote: "numero_pedido" (texto)
   - Transferencia: carpeta /salida/{numero_pedido}/

   ¿Quieres que ajuste algo?
```

---

## 🛠️ Stack tecnológico

<table>
<tr>
<td align="center" width="14%"><strong>🐍<br>Python 3.14</strong><br><sub>Runtime</sub></td>
<td align="center" width="14%"><strong>🖼️<br>PySide6</strong><br><sub>UI Framework</sub></td>
<td align="center" width="14%"><strong>🗄️<br>SQLAlchemy 2</strong><br><sub>ORM + SQLite</sub></td>
<td align="center" width="14%"><strong>📸<br>OpenCV</strong><br><sub>Imagen</sub></td>
<td align="center" width="14%"><strong>📄<br>PyMuPDF</strong><br><sub>PDF/PDF-A</sub></td>
<td align="center" width="14%"><strong>🔒<br>Fernet</strong><br><sub>Cifrado</sub></td>
<td align="center" width="14%"><strong>🔍<br>RapidOCR</strong><br><sub>OCR offline</sub></td>
</tr>
</table>

<details>
<summary>📦 Dependencias completas</summary>

| Categoría | Paquete | Versión |
|-----------|---------|---------|
| **UI** | PySide6 | 6.10.2 |
| **BD** | SQLAlchemy | 2.0.48 |
| **BD** | Alembic | 1.18.4 |
| **Barcode** | pyzbar | 0.1.9 |
| **Barcode** | zxing-cpp | 3.0.0 |
| **Imagen** | opencv-python | 4.13.0.92 |
| **Imagen** | Pillow | 12.1.1 |
| **OCR** | rapidocr-onnxruntime | 1.2.3 |
| **OCR** | pytesseract | 0.3.13 |
| **IA** | anthropic | 0.84.0 |
| **IA** | openai | 2.26.0 |
| **PDF** | PyMuPDF | 1.27.1 |
| **HTTP** | httpx | 0.28.1 |
| **Config** | pydantic-settings | 2.13.1 |
| **Config** | platformdirs | 4.9.4 |
| **Seguridad** | cryptography | 46.0.5 |
| **Scanner** | python-sane | 2.9.1 |
| **Automatización** | watchdog | 6.0.0 |
| **Automatización** | APScheduler | 3.11.2 |

</details>

---

## 📋 Configurador

El configurador permite ajustar cada aplicación a través de **6 pestañas**:

| Pestaña | Contenido |
|---------|-----------|
| ⚙️ **General** | Nombre, color, auto-transferencia, detección de blancos, barcode manual |
| 🖼️ **Imagen** | Formato captura, modo color, compresión, calidad |
| 📝 **Campos** | Campos de lote e indexación (texto, fecha, número, booleano, desplegable) |
| 🔄 **Pipeline** | Editor visual de pasos arrastrables |
| 📜 **Eventos** | Scripts para 7+ eventos del ciclo de vida |
| 📤 **Transferencia** | Destino, formato salida, naming pattern, política de colisión |

---

## ⌨️ Atajos de teclado

| Atajo | Acción |
|-------|--------|
| `Ctrl+S` | Escanear |
| `Ctrl+I` | Importar ficheros |
| `Ctrl+T` | Transferir lote |
| `Ctrl+P` | Reprocesar página |
| `←` / `→` | Página anterior / siguiente |
| `Home` / `End` | Primera / última página |
| `Ctrl+→` | Siguiente barcode |
| `Ctrl+Shift+→` | Siguiente página con revisión |
| `Ctrl++` / `Ctrl+-` | Zoom in / out |
| `Ctrl+F` | Ajustar a ventana |
| `Ctrl+0` | Zoom 100% |
| `R` / `Shift+R` | Rotar derecha / izquierda |
| `M` | Marcar/desmarcar página |
| `Del` | Eliminar página |
| `Ctrl+W` | Cerrar lote |

---

## 🔒 Seguridad

- 🔐 **API keys cifradas** con Fernet (AES-128-CBC + HMAC-SHA256) en `~/.local/share/docscan/secrets.enc`
- 🔑 **Clave de cifrado** generada automáticamente con permisos `0600`
- 🛡️ **Sanitización de rutas** para prevenir path traversal
- 🗃️ **SQLite WAL mode** obligatorio para concurrencia segura
- ⏱️ **Script timeout** configurable (por defecto 30s)
- 📝 **Scripts aislados**: errores no detienen el pipeline

---

## 🧪 Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v --tb=short

# Tests de un módulo específico
pytest tests/test_pipeline.py -v

# Test individual
pytest tests/test_pipeline.py::TestExecutor::test_barcode_step -v

# Con cobertura (necesita pytest-cov)
pytest tests/ --cov=app --cov-report=html
```

**Estado actual: 813 tests ✅ — 0 fallos**

---

## 📁 Formatos soportados

### Entrada (importación)
| Formato | Extensiones |
|---------|-------------|
| TIFF | `.tif`, `.tiff` (incluye multi-página) |
| JPEG | `.jpg`, `.jpeg` |
| PNG | `.png` |
| BMP | `.bmp` |
| PDF | `.pdf` (rasterizado con PyMuPDF) |

### Salida (transferencia)
| Formato | Características |
|---------|----------------|
| TIFF | Compresión LZW/JPEG/Deflate, multi-página |
| JPEG | Calidad configurable (1-100) |
| PNG | Sin pérdida |
| BMP | Sin compresión |
| PDF | Estándar |
| PDF/A | PDF/A-1b y PDF/A-2b para archivo a largo plazo |

---

## 🗺️ Roadmap

- [x] ~~Pipeline composable con 4 tipos de paso~~
- [x] ~~Doble motor de barcode (pyzbar + zxing-cpp)~~
- [x] ~~Triple motor OCR (RapidOCR + EasyOCR + Tesseract)~~
- [x] ~~Integración IA (Anthropic + OpenAI)~~
- [x] ~~Motor de scripting Python~~
- [x] ~~Workbench con visor, miniaturas y overlays~~
- [x] ~~Gestor de lotes con historial~~
- [x] ~~Transferencia simple y avanzada~~
- [x] ~~Internacionalización (ES/EN/CAT)~~
- [x] ~~AI Mode — asistente conversacional~~
- [x] ~~Export/Import de aplicaciones (.docscan)~~
- [x] ~~Detección de páginas en blanco~~
- [ ] 📖 Documentación de usuario
- [ ] 📦 Instaladores Linux + Windows
- [ ] 🔄 Auto-actualización via GitHub Releases
- [ ] 🌐 Documentación web (MkDocs)

---

## 👥 Créditos

Desarrollado por **Tecnomedia** — Soluciones de gestión documental.

---

<p align="center">
  <sub>DocScan Studio v0.1 RC — Hecho con ❤️ y 🐍</sub>
</p>
