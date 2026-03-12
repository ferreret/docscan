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
- [ ] La app aparece en la lista del Launcher
- [ ] Doble-click abre el Workbench sin errores
- [ ] El título muestra "DocScan Studio — Test Manual"

---

## 2. Pipeline con BarcodeStep

**Prerrequisitos**: App "Test Manual" creada.

**Pasos**:
1. Click en "Configurar" en la app
2. Pestaña Pipeline
3. Añadir paso "Barcode" (Motor 1 — pyzbar)
4. Guardar

**Verificaciones**:
- [ ] El paso aparece en la lista del pipeline
- [ ] Al guardar, no hay errores
- [ ] Al reabrir el configurador, el paso sigue ahí

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
- [ ] El script compila sin errores (no hay warning en log)
- [ ] Al importar una imagen con barcode, el script asigna roles
- [ ] `page.fields['barcode_count']` se refleja en la indexación

---

## 4. Editor VS Code

**Prerrequisitos**: VS Code instalado (`code` en PATH).

**Pasos**:
1. Configurador > Pipeline > Editar paso Script
2. Click en "Abrir en VS Code"
3. Modificar el código en VS Code
4. Cerrar la pestaña de VS Code (Ctrl+W)

**Verificaciones**:
- [ ] VS Code se abre con stubs de contexto al inicio
- [ ] Los stubs están marcados con delimitadores
- [ ] Al cerrar, el código modificado aparece en el diálogo
- [ ] Los stubs NO se incluyen en el código guardado

---

## 5. Campos de lote

**Prerrequisitos**: App con campos de lote definidos en configurador.

**Pasos**:
1. Configurador > Pestaña "Campos de lote"
2. Añadir campo "referencia" (texto), "fecha" (fecha)
3. Guardar, abrir Workbench

**Verificaciones**:
- [ ] Los campos aparecen en la pestaña "Lote" del panel de metadatos
- [ ] Se pueden editar los valores
- [ ] Un script puede leer `batch.fields` con los valores introducidos

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
- [ ] Thumbnail aparece en panel izquierdo
- [ ] Barcodes detectados aparecen en panel de barcodes
- [ ] Overlays de barcode visibles en el visor
- [ ] Barra de progreso muestra avance
- [ ] Estado final: "Procesamiento completado"

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
- [ ] Mensaje aparece en log tras completar el pipeline
- [ ] `batch.page_count` y `batch.state` tienen valores correctos

---

## 8. Transferencia simple (carpeta)

**Prerrequisitos**: Transferencia configurada con modo "folder".

**Pasos**:
1. Configurador > Pestaña "Transferencia"
2. Modo: Carpeta, Destino: `/tmp/docscan_test`
3. Guardar, abrir Workbench, importar, click "Transferir"

**Verificaciones**:
- [ ] Diálogo de confirmación aparece
- [ ] Archivos copiados a `/tmp/docscan_test/batch_N/`
- [ ] Mensaje "Transferencia completada" con conteo
- [ ] Estado del lote cambia a "exported"

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
- [ ] El script se ejecuta en lugar de la transferencia estándar
- [ ] No bloquea la UI (se ejecuta en QThread)
- [ ] Mensaje de éxito al terminar

---

## 10. Escáner SANE (requiere hardware)

**Prerrequisitos**: Escáner conectado, python-sane instalado.

**Pasos**:
1. Workbench > Radio "Escáner"
2. Seleccionar dispositivo del combo
3. Source type: "Flatbed"
4. Click "Escanear / Importar"

**Verificaciones**:
- [ ] Lista de escáneres se puebla
- [ ] Imagen capturada aparece como thumbnail
- [ ] Pipeline se ejecuta sobre la imagen

---

## 11. Escáner ADF (requiere hardware con alimentador)

**Prerrequisitos**: Escáner con ADF conectado.

**Pasos**:
1. Workbench > Radio "Escáner"
2. Source type: "ADF"
3. Colocar varias hojas en el alimentador
4. Click "Escanear / Importar"

**Verificaciones**:
- [ ] Múltiples páginas capturadas (una por hoja)
- [ ] Todas las thumbnails aparecen
- [ ] Pipeline se ejecuta en cada página

---

## 12. Navegación scriptable

**Prerrequisitos**: Evento `on_navigate_next` definido.

**Pasos**:
1. Configurador > Eventos > `on_navigate_next`
2. Código:

```python
def on_navigate_next(app, batch):
    # Saltar a la última página siempre
    return 999  # El workbench clampea al rango válido
```

3. Importar varias páginas, usar botón "Siguiente"

**Verificaciones**:
- [ ] Si retorna un índice válido, navega a esa página
- [ ] Si retorna valor fuera de rango, navegación estándar
- [ ] Si no hay evento, navegación normal (+1)

---

## 13. Batch manager

**Prerrequisitos**: Varios lotes existentes.

**Pasos**:
1. Launcher > Click "Gestor de lotes"
2. Verificar lista de lotes con filtros
3. Click en un lote > "Abrir"

**Verificaciones**:
- [ ] Lista muestra todos los lotes
- [ ] Filtros por estado funcionan
- [ ] Abrir lote carga páginas correctamente

---

## 14. Drag & drop

**Prerrequisitos**: Workbench abierto.

**Pasos**:
1. Arrastrar un archivo .jpg/.png/.pdf desde el explorador al Workbench

**Verificaciones**:
- [ ] El archivo se importa automáticamente
- [ ] Pipeline se ejecuta
- [ ] Thumbnail aparece

---

## 15. Re-procesamiento (Ctrl+P)

**Prerrequisitos**: Página ya procesada visible en el visor.

**Pasos**:
1. Navegar a una página procesada
2. Ctrl+P

**Verificaciones**:
- [ ] Pipeline se re-ejecuta en la página actual
- [ ] Resultados actualizados (barcodes, OCR, etc.)
- [ ] Mensaje "Re-procesado completado"
