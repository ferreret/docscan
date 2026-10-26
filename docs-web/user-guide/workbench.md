# :material-monitor: Workbench

El Workbench es la ventana de explotación donde se realiza la captura y procesamiento diario.

![Workbench de DocScan Studio](../assets/screenshots/workbench_full.png)

## Áreas de la interfaz

El Workbench se compone de cinco áreas:

1. **Barra de herramientas** — Escanear, importar, transferir, cerrar lote
2. **Panel de miniaturas** — Miniaturas con estados de color; la de la página que
   se ve en el visor lleva un marco del color de acento
3. **Visor de documentos** — Imagen con zoom, pan y recuadros de barcodes, con su
   barra de herramientas debajo
4. **Panel derecho** — Barcodes de la página, campos de lote y las pestañas
   Verificación / OCR / Log (ver más abajo)
5. **Barra de estado** — Mensajes y contadores del lote (páginas, con barcode,
   separadores y a revisión)

## Panel derecho

Funciona como en FlexibarNET 10. De arriba abajo:

- **BARCODES DE LA PÁGINA · N** — una fila por código: punto de color (el mismo que
  su recuadro en el visor), valor, «simbología · motor · rol» y el distintivo
  **MANUAL** si se añadió a mano. Crece hasta 280 px y luego hace scroll.
    - Pasar el ratón por una fila resalta su recuadro en el visor, y al revés.
    - **+ Añadir**, **Ctrl+N** o **Insert** añaden un código a mano.
    - La papelera de la fila, o **Supr** con la fila seleccionada, lo borran sin
      preguntar: **Ctrl+Z** deshace la última edición de códigos.
- **CAMPOS DE LOTE · N** — los campos de lote de la aplicación (solo si tiene).
  Crece hasta 180 px.
- **Pestañas** — **Verificación** (panel de la aplicación, si tiene), **OCR**
  (texto de la página) y **Log**.

Los dos paneles se pliegan con su flecha. Qué paneles y pestañas se ven, y el orden
de las pestañas, se configura por aplicación en **Configurador → General →
Pestañas del Workbench**; ahí también se puede ocultar **+ Añadir**.

Al abrir una página a revisión, la barra de estado muestra el motivo y cuántos
errores de procesado tiene (el detalle, en la pestaña Log).

## Estados de página

Las miniaturas muestran el estado mediante bordes de color:

| Color | Estado |
|-------|--------|
| :material-circle:{ style="color: #f0718c" } Rojo | A revisión o excluida |
| :material-circle:{ style="color: #f97316" } Naranja | Página separadora |
| :material-circle:{ style="color: #60a5fa" } Azul | Con campos de indexación |
| :material-circle:{ style="color: #4ade80" } Verde | Con códigos de barras |
| :material-circle:{ style="color: #9fadc7" } Gris | Sin reconocimiento |

## Visor de documentos

El visor central permite:

- **Zoom**: Ctrl++ / Ctrl+- o rueda del ratón
- **Pan**: Clic y arrastrar
- **Ajustar a ventana**: Ctrl+F
- **Rotar**: R (derecha) / Shift+R (izquierda)
- **Overlays**: Visualización de barcodes y regiones OCR sobre la imagen

## Escaneo

1. Opcionalmente marcar **Configurar escáner** para ajustar opciones
2. Clic en **Escanear** (o Ctrl+S)
3. Las páginas se importan y procesan automáticamente por el pipeline

## Importación

- Clic en **Importar** (Ctrl+I) y seleccionar ficheros
- O **arrastrar** ficheros directamente sobre el visor
- Formatos: TIFF (multi-página), JPEG, PNG, BMP, PDF
