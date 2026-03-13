# Guia de pruebas manuales — DocScan Studio

## Prerrequisitos generales

- Python 3.14 con entorno virtual activado
- BD inicializada (`alembic upgrade head` o primera ejecución)
- Al menos una aplicación creada en el Launcher

---

## 1. Crear aplicación

**Prerrequisitos**: Launcher abierto.

**Pasos**:
1. Click en "Nueva aplicación"
2. Nombre: "Test Manual", Descripción: "Prueba"
3. Guardar

**Verificaciones**:
- [x] La app aparece en la lista del Launcher
- [x] Doble-click abre el Workbench sin errores
- [x] El título muestra "DocScan Studio — Test Manual"

---

## 2. Pipeline con BarcodeStep

**Prerrequisitos**: App "Test Manual" creada.

**Pasos**:
1. Click en "Configurar" en la app
2. Pestaña Pipeline
3. Añadir paso "Barcode" (Motor 1 — pyzbar)
4. Guardar

**Verificaciones**:
- [x] El paso aparece en la lista del pipeline
- [x] Al guardar, no hay errores
- [x] Al reabrir el configurador, el paso sigue ahí

---

## 3. Script post-barcode

**Prerrequisitos**: Pipeline con BarcodeStep configurado.

**Pasos**:
1. Configurador > Pipeline > Añadir paso "Script"
2. Entry point: `process`
3. Código:

```python
def process(app, batch, page, pipeline):
    for bc in page.barcodes:
        if bc.value.startswith("SEP"):
            bc.role = "separator"
        else:
            bc.role = "content"
    page.fields['barcode_count'] = len(page.barcodes)
    log.info("Barcodes procesados: %d", len(page.barcodes))
```

4. Guardar

**Verificaciones**:
- [x] El script compila sin errores (no hay warning en log)
- [x] Al importar una imagen con barcode, el script asigna roles
- [x] `page.fields['barcode_count']` se refleja en la indexación

---

## 4. Editor VS Code

**Prerrequisitos**: VS Code instalado (`code` en PATH).

**Pasos**:
1. Configurador > Pipeline > Editar paso Script
2. Click en "Abrir en VS Code"
3. Modificar el código en VS Code
4. Cerrar la pestaña de VS Code (Ctrl+W)

**Verificaciones**:
- [x] VS Code se abre con stubs de contexto al inicio
- [x] Los stubs están marcados con delimitadores
- [x] Al cerrar, el código modificado aparece en el diálogo
- [x] Los stubs NO se incluyen en el código guardado

---

## 5. Campos de lote

**Prerrequisitos**: App con campos de lote definidos en configurador.

**Pasos**:
1. Configurador > Pestaña "Campos de lote"
2. Añadir campo "referencia" (texto), "fecha" (fecha)
3. Guardar, abrir Workbench

**Verificaciones**:
- [x] Los campos aparecen en la pestaña "Lote" del panel de metadatos
- [x] Se pueden editar los valores
- [x] Un script puede leer `batch.fields` con los valores introducidos

Script de verificación:
```python
def process(app, batch, page, pipeline):
    log.info("Referencia: %s", batch.fields.get('referencia', 'N/A'))
    log.info("Campos def: %s", app.batch_fields_def)
```

---

## 6. Importar + procesar

**Prerrequisitos**: Pipeline con barcode + script configurado.

**Pasos**:
1. Workbench > Radio "Importar" > Click "Escanear / Importar"
2. Seleccionar una imagen con barcode (o PDF)
3. Esperar procesamiento

**Verificaciones**:
- [x] Thumbnail aparece en panel izquierdo
- [x] Barcodes detectados aparecen en panel de barcodes
- [x] Overlays de barcode visibles en el visor
- [x] Barra de progreso muestra avance
- [x] Estado final: "Procesamiento completado"

---

## 7. Eventos (on_scan_complete)

**Prerrequisitos**: App con evento definido.

**Pasos**:
1. Configurador > Pestaña "Eventos"
2. Seleccionar `on_scan_complete`
3. Código:

```python
def on_scan_complete(app, batch):
    log.info("=== SCAN COMPLETE: lote %d, app %s ===", batch.id, app.name)
    log.info("Páginas: %d, Estado: %s", batch.page_count, batch.state)
```

4. Guardar, abrir Workbench, importar imagen

**Verificaciones**:
- [x] Mensaje aparece en log tras completar el pipeline
- [x] `batch.page_count` y `batch.state` tienen valores correctos

---

## 8. Transferencia simple (carpeta)

**Prerrequisitos**: Transferencia configurada con modo "folder".

**Pasos**:
1. Configurador > Pestaña "Transferencia"
2. Modo: Carpeta, Destino: `/tmp/docscan_test`
3. Guardar, abrir Workbench, importar, click "Transferir"

**Verificaciones**:
- [x] Diálogo de confirmación aparece
- [x] Archivos copiados a `/tmp/docscan_test/batch_N/`
- [x] Mensaje "Transferencia completada" con conteo
- [x] Estado del lote cambia a "exported"

---

## 9. Transferencia avanzada (on_transfer_advanced)

**Prerrequisitos**: Evento `on_transfer_advanced` definido.

**Pasos**:
1. Configurador > Eventos > `on_transfer_advanced`
2. Código:

```python
def on_transfer_advanced(app, batch, pages):
    log.info("Transferencia avanzada: %d páginas", len(pages))
    for p in pages:
        log.info("  Página %d: %s", p['page_index'], p['image_path'])
    # Retornar True indica éxito
    return True
```

3. Guardar, importar, transferir

**Verificaciones**:
- [x] El script se ejecuta en lugar de la transferencia estándar
- [x] No bloquea la UI (se ejecuta en QThread)
- [x] Mensaje de éxito al terminar

---

## 10. Escáner SANE (requiere hardware)

**Prerrequisitos**: Escáner conectado, python-sane instalado.

**Pasos**:
1. Workbench > Radio "Escáner"
2. Seleccionar dispositivo del combo
3. Source type: "Flatbed"
4. Click "Escanear / Importar"

**Verificaciones**:
- [x] Lista de escáneres se puebla
- [x] Imagen capturada aparece como thumbnail
- [x] Pipeline se ejecuta sobre la imagen

---

## 11. Escáner ADF (requiere hardware con alimentador)

**Prerrequisitos**: Escáner con ADF conectado.

**Pasos**:
1. Workbench > Radio "Escáner"
2. Source type: "ADF"
3. Colocar varias hojas en el alimentador
4. Click "Escanear / Importar"

**Verificaciones**:
- [x] Múltiples páginas capturadas (una por hoja)
- [x] Todas las thumbnails aparecen
- [x] Pipeline se ejecuta en cada página

---

## 12. Navegación scriptable

**Prerrequisitos**: Evento `on_navigate_next` definido, varias páginas importadas (algunas con barcode, otras sin).

**Pasos**:
1. Configurador > Eventos > `on_navigate_next`
2. Código:

```python
def on_navigate_next(app, batch, current_page_index, total_pages):
    # Saltar páginas pares (ejemplo simple de navegación custom)
    next_idx = current_page_index + 2
    if next_idx < total_pages:
        log.info("Saltando a página %d (skip par)", next_idx)
        return next_idx
    log.info("No hay más páginas, navegación estándar")
    return None  # None = navegación estándar (+1)
```

3. Importar varias páginas (mezcla con y sin barcode), usar botón "Siguiente"

**Verificaciones**:
- [x] Si retorna un índice válido, navega a esa página
- [x] Si retorna valor fuera de rango, navegación estándar
- [x] Si no hay evento, navegación normal (+1)

---

## 13. Batch manager

**Prerrequisitos**: Varios lotes existentes.

**Pasos**:
1. Launcher > Click "Gestor de lotes"
2. Verificar lista de lotes con filtros
3. Click en un lote > "Abrir"

**Verificaciones**:
- [x] Lista muestra todos los lotes
- [x] Filtros por estado funcionan
- [x] Abrir lote carga páginas correctamente

---

## 14. Drag & drop

**Prerrequisitos**: Workbench abierto.

**Pasos**:
1. Arrastrar un archivo .jpg/.png/.pdf desde el explorador al Workbench

**Verificaciones**:
- [x] El archivo se importa automáticamente
- [x] Pipeline se ejecuta
- [x] Thumbnail aparece

---

## 15. Re-procesamiento (Ctrl+P)

**Prerrequisitos**: Página ya procesada visible en el visor.

**Pasos**:
1. Navegar a una página procesada
2. Ctrl+P

**Verificaciones**:
- [x] Pipeline se re-ejecuta en la página actual
- [x] Resultados actualizados (barcodes, OCR, etc.)
- [x] Mensaje "Re-procesado completado"
