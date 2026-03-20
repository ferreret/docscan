# Pruebas manuales — Release 1B (ImageLib + Formato + Correcciones)

Guia de pruebas manuales para verificar todas las funcionalidades nuevas.
Marcar cada prueba con [x] al completarla.

---

## 1. Configurador — Pestana Imagen

### 1.1 Estructura de pestanas
- [x] Abrir Launcher, crear o editar una aplicacion
- [x] Verificar que hay 6 pestanas: General | **Imagen** | Campos de Lote | Pipeline | Eventos | Transferencia
- [x] Verificar que la pestana General ya NO tiene el combo "Formato de salida"

### 1.2 Visibilidad condicional por formato
- [x] En pestana Imagen, seleccionar formato **tiff**: aparece "Compresion" (lzw/zip/none/group4), se ocultan calidad JPEG y compresion PNG
- [x] Seleccionar formato **jpg**: aparece "Calidad JPEG", se ocultan compresion TIFF y PNG
- [x] Seleccionar formato **png**: aparece "Compresion PNG", se ocultan compresion TIFF y calidad JPEG

### 1.3 Visibilidad condicional por modo color
- [x] Seleccionar modo color **bw**: aparece "Umbral B/N"
- [x] Seleccionar modo color **color** o **grayscale**: se oculta "Umbral B/N"

### 1.4 Rango de valores
- [x] ~~DPI: acepta 72 a 1200, no permite valores fuera de rango~~ (DPI eliminado de ImageConfig, lo controla el escaner)
- [x] Calidad JPEG: acepta 1 a 100
- [x] Compresion PNG: acepta 0 a 9
- [x] Umbral B/N: acepta 0 a 255

### 1.5 Persistencia
- [x] Configurar formato=jpg, color=grayscale, calidad=50
- [x] Guardar la aplicacion
- [x] Cerrar y reabrir el configurador: los valores se mantienen
- [x] Nota informativa visible: "Los archivos importados se almacenan en su formato original."

---

## 2. Escaneo con ImageConfig

### 2.1 Escaneo JPEG calidad baja
- [x] Configurar app: formato=jpg, calidad=50
- [x] Abrir workbench, escanear una pagina
- [x] Verificar en `~/.local/share/docscan/images/app_X/batch_Y/` que la imagen es .jpg
- [x] Verificar que el tamano del fichero es razonablemente pequeno (calidad 50)

### 2.2 Escaneo TIFF con compresion
- [x] Configurar app: formato=tiff, compresion=lzw
- [x] Escanear una pagina
- [x] Verificar que se genera un .tiff en la carpeta del lote

### 2.3 Escaneo PNG
- [x] Configurar app: formato=png, compresion=6
- [x] Escanear y verificar que se genera un .png

### 2.4 Escaneo en escala de grises
- [x] Configurar app: formato=tiff, color=grayscale
- [x] Escanear una pagina en color
- [x] Abrir el fichero resultante: debe ser escala de grises (1 canal)

### 2.5 Escaneo en blanco y negro
- [x] Configurar app: formato=tiff, color=bw, umbral=128
- [x] Escanear una pagina
- [x] Abrir el fichero: debe ser binario (solo blanco y negro, sin grises)

### 2.6 Importacion NO aplica ImageConfig
- [x] Con la misma app (formato=jpg, calidad=50), importar un PDF o una imagen PNG
- [x] Verificar que el fichero almacenado NO se convierte a JPEG — se mantiene en su formato original (se guardara con la extension del formato de la app pero via cv2.imwrite, no Pillow con calidad)
- [x] **Nota**: actualmente la importacion solo aplica ImageConfig a paginas escaneadas; las importadas usan el path directo

---

## 3. Configurador — Formato de salida en Transferencia

### 3.1 Visibilidad por modo
- [x] En pestana Transferencia, seleccionar modo **folder**: aparece grupo "Conversion al transferir (modo carpeta)", se ocultan "Opciones PDF" y "Opciones CSV"
- [x] Seleccionar modo **pdf** o **pdfa**: aparece grupo "Opciones PDF", se ocultan "Conversion al transferir" y "Opciones CSV"
- [x] Seleccionar modo **csv**: aparece grupo "Opciones CSV", se ocultan los otros dos grupos

### 3.2 Visibilidad por formato de salida
- [x] En modo folder, formato de salida **(original)**: se ocultan calidad JPEG, compresion TIFF, compresion PNG
- [x] Seleccionar **jpg**: aparece "Calidad JPEG"
- [x] Seleccionar **tiff**: aparece "Compresion TIFF"
- [x] Seleccionar **png**: aparece "Compresion PNG"

### 3.3 DPI de salida
- [x] Verificar que DPI=0 muestra texto "(original)" en el spin box
- [x] Verificar que se puede poner hasta 1200

> **Notas:**
> - El campo DPI esta dentro del grupo "Conversion al transferir (modo carpeta)", visible solo en modo **folder**.
> - Cuando el valor es **0**, el spin box muestra "(original)". Esto indica que no se redimensionara la imagen al transferir.
> - Cuando el valor es > 0 (ej: 150), se muestra con sufijo " DPI" (ej: "150 DPI").
> - Rango valido: **0** (original) a **1200**. No se aceptan valores negativos ni superiores a 1200.

### 3.4 Color de salida
- [x] Verificar opciones: (original), grayscale, bw
- [x] Verificar que aparece nota: "Solo reduce: color → gris → B/N. No es posible recuperar color a partir de gris o B/N."

### 3.5 Calidad JPEG PDF
- [x] En modo pdf/pdfa, verificar que en grupo "Opciones PDF" aparece "Calidad JPEG:" con rango 1-100 y "DPI del PDF:" con rango 72-600

### 3.6 Persistencia
- [x] Configurar formato salida=jpg, DPI=150, color=grayscale, calidad=60
- [x] Guardar, cerrar, reabrir: valores se mantienen
- [x] Configurar modo pdf, calidad JPEG PDF=70, guardar, reabrir: se mantiene

---

## 4. Transferencia a carpeta con conversion

### 4.1 Conversion de formato
- [x] Configurar app: formato interno=tiff (pestana Imagen)
- [x] Configurar transferencia: modo=folder, formato salida=jpg, calidad=75, destino=/tmp/test_transfer
- [x] Escanear varias paginas
- [x] Transferir
- [x] Verificar en la carpeta destino: los ficheros son .jpg (no .tiff)
- [x] Verificar que los ficheros se pueden abrir correctamente

### 4.2 Conversion de formato TIFF a PNG
- [x] Configurar salida=png, compresion=9
- [x] Transferir
- [x] Verificar que los ficheros de destino son .png

### 4.3 Conversion de color al transferir
- [x] Almacenar paginas en color (ImageConfig color=color)
- [x] Transferir con color de salida=grayscale
- [x] Verificar que las imagenes en la carpeta destino son escala de grises

### 4.4 Conversion a blanco y negro al transferir
- [x] Transferir con color de salida=bw
- [x] Verificar que las imagenes son binarias (solo 0 y 255)

### 4.5 Cambio de DPI al transferir
- [x] Almacenar a 300 DPI
- [x] Transferir con DPI salida=150
- [x] Verificar que las imagenes de salida tienen aproximadamente la mitad de dimensiones

### 4.6 Sin conversion (original)
- [x] Dejar formato de salida en "(original)", color en "(original)", DPI en 0
- [x] Transferir
- [x] Verificar que se hace copia directa (shutil.copy2), el fichero destino es identico al origen

### 4.7 Combinacion: formato + color + DPI
- [x] Configurar salida=jpg, DPI=150, color=grayscale, calidad=50
- [x] Transferir
- [x] Verificar: fichero .jpg, gris, tamano reducido, calidad baja (fichero pequeno)

---

## 5. Transferencia PDF con calidad configurable

### 5.1 Calidad alta
- [x] Configurar transferencia: modo=pdf, calidad JPEG PDF=95
- [x] Transferir un lote con varias paginas
- [x] Verificar que se genera un PDF con todas las paginas
- [x] Anotar tamano del PDF

### 5.2 Calidad baja
- [x] Configurar calidad JPEG PDF=30
- [x] Transferir el mismo lote
- [x] Verificar que el PDF se genera correctamente
- [x] El PDF debe ser significativamente mas pequeno que con calidad 95

---

## 6. ImageLib desde scripts

### 6.1 ImageLib disponible en namespace
- [x] Crear una app con un ScriptStep en el pipeline con este codigo:
```python
def process(app, batch, page, pipeline):
    log.info(f"ImageLib disponible: {ImageLib}")
    log.info(f"Modo color imagen: {ImageLib.get_color_mode(page.image)}")
```
- [x] Procesar una pagina, verificar en el log que aparece "ImageLib disponible" y el modo de color

### 6.2 ImageLib.merge_to_pdf desde script
- [x] Crear un evento `on_transfer_advanced` con este codigo:
```python
def on_transfer_advanced(app, batch, pages):
    imgs = [p.image for p in pages if p.image is not None]
    if imgs:
        output = Path("/tmp/test_imagelib_merge.pdf")
        ImageLib.merge_to_pdf(imgs, output, dpi=200, quality=80)
        log.info(f"PDF generado: {output}")
```
- [x] Procesar y transferir un lote
- [x] Verificar que `/tmp/test_imagelib_merge.pdf` existe y contiene las paginas

### 6.3 ImageLib.save desde script con parametros
- [x] ScriptStep:
```python
def process(app, batch, page, pipeline):
    output = Path(f"/tmp/test_page_{page.page_index}.jpg")
    ImageLib.save(page.image, output, quality=50, dpi=200)
    log.info(f"Imagen guardada: {output} ({output.stat().st_size} bytes)")
```
- [x] Procesar y verificar que `/tmp/test_page_0.jpg` existe con tamano razonable

### 6.4 ImageLib.to_grayscale desde script
- [x] ScriptStep:
```python
def process(app, batch, page, pipeline):
    gray = ImageLib.to_grayscale(page.image)
    log.info(f"Original: {page.image.shape}, Gris: {gray.shape}")
    pipeline.replace_image(gray)
```
- [x] Procesar y verificar que la imagen en el visor es gris tras el pipeline

### 6.5 ImageLib.split desde script
- [x] ScriptStep (con un PDF importado):
```python
def process(app, batch, page, pipeline):
    pages = ImageLib.split("/ruta/a/multipagina.pdf", "/tmp/split_out", format="png", dpi=200)
    log.info(f"Split: {len(pages)} paginas")
```
- [x] Verificar que se generan imagenes PNG en `/tmp/split_out/`

### 6.6 ImageLib.get_dpi y resize_to_dpi desde script
```python
def process(app, batch, page, pipeline):
    # Guardar con DPI conocido
    tmp = Path("/tmp/test_dpi.tiff")
    ImageLib.save(page.image, tmp, dpi=300)
    dpi = ImageLib.get_dpi(tmp)
    log.info(f"DPI: {dpi}")

    # Resize
    resized = ImageLib.resize_to_dpi(page.image, 300, 150)
    log.info(f"Original: {page.image.shape}, Resized: {resized.shape}")
```
- [x] Verificar DPI=300 en el log y que las dimensiones se reducen a la mitad

### 6.7 ImageLib disponible en eventos de ciclo de vida
- [x] Crear un evento `on_app_start` con:
```python
def on_app_start(app):
    log.info(f"ImageLib en evento: {ImageLib}")
```
- [x] Abrir la app, verificar en el log que aparece "ImageLib en evento"

---

## 7. Script timeout (C2)

### 7.1 Script que excede timeout
- [x] Crear un ScriptStep con:
```python
import time
def process(app, batch, page, pipeline):
    time.sleep(60)  # Excede el timeout de 30s
```
- [x] Procesar una pagina
- [x] Verificar que:
  - El pipeline NO se queda colgado indefinidamente
  - Aparece error "ScriptTimeoutError" en el log o en page.flags
  - Las demas paginas continuan procesandose

### 7.2 Script rapido funciona normalmente
- [x] Crear un ScriptStep con:
```python
def process(app, batch, page, pipeline):
    log.info("Script rapido OK")
```
- [x] Verificar que se ejecuta sin problemas

---

## 8. Eliminacion de AiStep y renombrado custom_fields (R1)

> AiStep fue eliminado; la funcionalidad IA se programa en ScriptStep con los SDKs.
> `ai_fields` se renombra a `custom_fields` en todo el sistema.

### 8.1 AiStep no aparece en el configurador
- [x] Abrir configurador de cualquier app, pestana Pipeline
- [x] Verificar que el combo de tipos de paso NO contiene "IA"
- [x] Solo deben aparecer: Imagen, Barcode, OCR, Script

### 8.2 Migracion renombra columna y limpia pasos AI
- [x] Ejecutar: `alembic upgrade head`
- [x] Verificar que no hay errores
- [x] Ejecutar: `sqlite3 ~/.local/share/docscan/docscan.db ".schema pages"`
- [x] Verificar que existe `custom_fields_json` y NO existe `ai_fields_json`

### 8.3 Pipeline antiguo con pasos AI se deserializa sin error
- [x] Si hay aplicaciones que tenian pasos AI, abrir su configurador
- [x] Verificar que la lista de pasos carga sin error (los pasos AI simplemente desaparecen)
- N/A: ningun pipeline existente contenia pasos AI

### 8.4 Scripts usan page.custom_fields
- [x] Crear un ScriptStep con:
```python
def process(app, batch, page, pipeline):
    page.custom_fields["test_key"] = "test_value"
    log.info(f"custom_fields: {page.custom_fields}")
```
- [x] Procesar una pagina
- [x] Verificar en el log que aparece `custom_fields: {'test_key': 'test_value'}`
- [x] Cerrar y reabrir el lote: el campo persiste (verificar en BD con sqlite3)

### 8.5 Transferencia exporta fields en metadatos
- [x] Configurar transferencia modo=folder con include_metadata=True
- [x] Transferir un lote que tenga fields
- [x] Abrir el fichero .json de metadatos junto a la imagen
- [x] Verificar que contiene la clave `"fields"` (no `"ai_fields"` ni `"custom_fields"`)

---

## 9. Alembic (C4)

### 9.1 Migracion en BD nueva
- [ ] Eliminar (o renombrar) la BD existente: `~/.local/share/docscan/docscan.db`
- [ ] Ejecutar: `python3.14 main.py` — las tablas se crean
- [ ] Ejecutar: `alembic stamp head` — marca la BD como actualizada
- [ ] Ejecutar: `alembic current` — muestra la revision actual
- [ ] Verificar que no hay errores

### 9.2 Migracion en BD existente
- [x] Con la BD actual (ya migrada), ejecutar: `alembic upgrade head`
- [x] Debe indicar que ya esta en la ultima revision (noop)

### 9.3 Columna image_config_json existe
- [x] Ejecutar:
```bash
sqlite3 ~/.local/share/docscan/docscan.db ".schema applications"
```
- [x] Verificar que la columna `image_config_json` aparece en el schema

### 9.4 Indices en batches
- [x] Ejecutar:
```bash
sqlite3 ~/.local/share/docscan/docscan.db ".indices batches"
```
- [x] Verificar que existen indices `ix_batches_application_id` y `ix_batches_state`

---

## 10. Dependencias fijadas (C3)

### 10.1 requirements.txt con versiones exactas
- [x] Abrir `requirements.txt`: todas las dependencias tienen `==` (no `>=`)
- [x] Verificar que no hay dependencias de test (pytest, ruff) en requirements.txt

### 10.2 requirements-dev.txt
- [x] Abrir `requirements-dev.txt`: incluye `-r requirements.txt` y dependencias de test
- [x] Ejecutar: `pip install -r requirements-dev.txt` — sin errores

---

## 11. Engine disposal (H1)

### 11.1 Cierre limpio
- [x] Abrir la app con `python3.14 main.py`
- [x] Cerrar la ventana del launcher (o el workbench)
- [x] Verificar en el log que no aparecen warnings de "engine not disposed" o conexiones huerfanas
- [x] Verificar que el proceso termina limpiamente (no queda colgado)

---

## 12. Window cleanup (H2)

### 12.1 Abrir y cerrar multiples workbenches
- [x] Abrir workbench de una app
- [x] Cerrarlo (vuelve al launcher)
- [x] Abrir otro workbench
- [x] Cerrarlo
- [x] Repetir 3-4 veces
- [x] Verificar que la app no consume memoria creciente (las ventanas se limpian)

### 12.2 Gestor de lotes
- [x] Abrir gestor de lotes desde el launcher
- [x] Cerrarlo
- [x] Abrirlo de nuevo
- [x] Verificar que funciona correctamente sin acumular instancias

---

## 13. Path traversal en transferencia (H3)

### 13.1 Patron con ".." se sanitiza
- [ ] Configurar patron de nombre: `../../etc/passwd_{page_index:04d}`
- [ ] Transferir un lote
- [ ] Verificar que los ficheros NO se escriben fuera de la carpeta destino
- [ ] Verificar que ".." se elimina del nombre

### 13.2 Patron con backslash se sanitiza
- [ ] Configurar patron: `sub\dir\{page_index:04d}`
- [ ] Transferir
- [ ] Verificar que las "\" se reemplazan por "_" en el nombre

### 13.3 Patron normal con subdirectorios funciona
- [ ] Configurar patron: `{batch_id}/{page_index:04d}`
- [ ] Transferir
- [ ] Verificar que se crea el subdirectorio correctamente

---

## 14. Worker wait reducido (H5)

### 14.1 Cierre rapido del workbench
- [x] Abrir un workbench, escanear unas paginas
- [x] Cerrar el workbench inmediatamente
- [x] Verificar que se cierra rapidamente (< 1 segundo), sin espera larga
- [x] Al reabrir el lote, las paginas pendientes se procesan automaticamente

---

## 15. Regresiones — funcionalidad existente

### 15.1 Escaneo basico sin ImageConfig
- [ ] Crear una app nueva (sin configurar pestana Imagen — valores por defecto)
- [ ] Escanear: funciona igual que antes (TIFF, 300 DPI, color)

### 15.2 Transferencia basica sin conversion
- [ ] Configurar transferencia modo=folder, formato salida=(original)
- [ ] Transferir: copia directa, igual que antes

### 15.3 Transferencia PDF sin cambios
- [ ] Configurar transferencia modo=pdf, DPI=200
- [ ] Transferir: genera PDF correctamente

### 15.4 Pipeline con barcode + script
- [ ] App con BarcodeStep + ScriptStep
- [ ] Procesar paginas: barcodes se detectan y scripts se ejecutan

### 15.5 Importacion de imagenes
- [ ] Importar carpeta con TIFF, PNG, JPEG
- [ ] Verificar que se importan todas correctamente

### 15.6 Importacion de PDF
- [ ] Importar un PDF de varias paginas
- [ ] Verificar que cada pagina aparece como pagina individual

### 15.7 Campos de lote
- [ ] Crear campos de lote en el configurador
- [ ] Abrir workbench, rellenar campos, transferir
- [ ] Verificar que los campos se interpolan en el nombre de fichero

### 15.8 Navegacion
- [ ] Navegar entre paginas con flechas, miniaturas
- [ ] Verificar zoom, pan en el visor

### 15.9 Panel de log
- [ ] Verificar que los mensajes de log aparecen en el panel

---

## Resumen de pruebas

| Seccion | Pruebas | Descripcion |
|---------|---------|-------------|
| 1       | 5       | Configurador tab Imagen |
| 2       | 6       | Escaneo con ImageConfig |
| 3       | 6       | Configurador formato salida |
| 4       | 7       | Transferencia con conversion |
| 5       | 2       | PDF calidad configurable |
| 6       | 7       | ImageLib desde scripts |
| 7       | 2       | Script timeout |
| 8       | 5       | Eliminacion AiStep + custom_fields |
| 9       | 4       | Alembic |
| 10      | 2       | Dependencias |
| 11      | 1       | Engine disposal |
| 12      | 2       | Window cleanup |
| 13      | 3       | Path traversal |
| 14      | 1       | Worker wait |
| 15      | 9       | Regresiones |
| **Total** | **62** | |
