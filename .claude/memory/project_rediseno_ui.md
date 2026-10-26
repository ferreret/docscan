---
name: project_rediseno_ui
description: Rediseño visual de DocScan con la estética de FlexibarNET10 — fases hechas y pendientes (rama feat/rediseno-ui)
metadata:
  type: project
---

El 2026-10-26 Nicolás pidió mejorar toda la estética, porque «hay que mejorarlo todo».
La propuesta está en `docs/estetica/propuesta_estetica_2026-10-26.md`.

La referencia es FlexibarNET10, por la regla de paridad
([[project_paridad_flexibarnet10]]). Rama: `feat/rediseno-ui`, que sale de
`fix/lote3-nada-falla-en-silencio`.

**Hecho:** commit `bf05ebc`, sin push.
- Barra del visor en su propia franja bajo la imagen. La pidió él: antes tapaba la página.
- **E1** — `app/ui/palette.py` es la fuente única de color, con los valores de Flexibar.
  La plantilla `resources/styles/theme.qss` usa `$tokens` y sustituye a `dark.qss` y
  `light.qss`. El Python pide colores con `palette.color("clave")`.
- **E3** — Inter (OFL) empaquetada en `resources/fonts/inter` y registrada en `main.py`.
  En Windows se usa Segoe UI.
- **E2** — Lucide 1.55.0 (ISC), 62 iconos en `resources/icons/lucide`. Se recolorean con
  `app/ui/icons.py` (`svg_icon(nombre, color)` / `icon(nombre, rol)`). Para añadir un
  icono: copiarlo del tarball `lucide-static`, fijando la versión, y comprobar el SHA-512.
- Contador «N / M» ajustado a su texto y centrado entre las flechas. Un test mide el
  centrado en píxeles con el QSS real.

- **Panel derecho como Flexibar** (2026-10-26). Diseño en
  `docs/estetica/panel_derecho_workbench.md`:
  - barcodes como lista de filas, panel de campos plegable, pestañas
    Verificación/OCR/Log;
  - visibilidad y orden por App, con las columnas `workbench_layout_json` y
    `hide_add_barcode_button` (migración `b4e2a7c9d1f3`, con `add_column` sin batch);
  - contadores del lote en la barra de estado;
  - Ctrl+N/Insert/Supr/Ctrl+Z;
  - hover fila ↔ recuadro;
  - corregidos dos stubs vacíos: OCR y `default_tab`.
- Miniatura seleccionada con marco macizo de acento.
- **E4a** (2026-10-26, commit en `feat/rediseno-ui`, sin push): barra superior como Flexibar.
  - Escanear F5, ⚙ (popover `scan_config_popup.py`: escáner + ↻, fuente, «mostrar
    opciones»), distintivo «Escáner: …», Importar… Ctrl+I, Procesar F9 (todo el
    lote, `_run_pipeline_on`), Transferir/Cerrar lote con contorno verde/rojo.
  - Sin radio buttons. Los escáneres se enumeran al abrir ⚙ o al escanear sin
    escáner, no al abrir el Workbench.
  - DocScan no tiene perfiles de escaneo: desviación consciente de Flexibar.

- **E4c** (2026-10-26, commit en `feat/rediseno-ui`, sin push): tarjetas del launcher y barras de estado.
  - `app/ui/launcher/app_card.py` deriva icono, acento y etiquetas con las reglas de
    `AppIconCatalog`/`AppCardTagDeriver` de Flexibar; el acento usa su mismo FNV-1a
    sobre UTF-16. Sin selector manual de icono (haría falta columna nueva).
  - Menú ⋮ / botón derecho; fuera la línea `_info_label` bajo la lista.
  - Workbench: «1240×1754 — N DPI», progreso 120×3 verde, «Procesado N/M (k errores)».
- **E4e/f** (2026-10-26, commit en `feat/rediseno-ui`, sin push): campo de fecha con icono de calendario
  (como el DatePicker de Flexibar), tic en todas las casillas, lista de pasos del
  Configurador con casilla real + icono/color por tipo (sin botón On/Off).
  - Token `$icons_dir` en `render_stylesheet` (ruta absoluta): los `url()` relativos
    dependían del directorio de trabajo. SVG temáticos en `resources/icons/*-{dark,light}.svg`.
  - Arreglado: arrastrar un paso no cambiaba el orden guardado (`rowsMoved`).
  - Corrección de E4c: el icono «escáner» sale del escáner recordado por el Workbench
    (`source/<id>/scanner_name`), no de `scanner_backend`, que el Configurador siempre rellena.
- **Hallazgo (no arreglado):** las páginas no guardan los DPI reales del escáner.
  `BatchService.add_pages` guarda con `cv2.imwrite` (los TIFF quedan con «1 DPI») o con
  `ImageLib.save(dpi=300)` fijo. `read_dpi` ignora < 50, pero el 300 fijo se muestra como
  si fuera real. Encaja con el lote 4 (escáner).

**Pendiente:** con E4e/f, las fases de la propuesta están todas hechas.
- Regenerar las capturas de la documentación con `tools/ui_snapshots.py` y rehacer la
  ficha del portfolio ([[project_ficha_portfolio]]).
- Quedan colores literales en `document_viewer.py` (la paleta de los recuadros de
  barcode sobre el papel), a propósito. Las tarjetas ya usan la paleta.

**Herramienta de capturas:** `tools/ui_snapshots.py` (hecha el 2026-10-26).
- Regenera las 15 capturas de `docs/screenshots` y `docs-web/assets/screenshots`, y con
  `--portfolio RUTA` también el WebP del portfolio ([[project_ficha_portfolio]]).
- Aísla XDG y QSettings, usa offscreen y datos neutros (Suministros Ejemplo S.L.).
- **Pendiente:** ejecutarla **al terminar el rediseño**. Las capturas de la documentación
  aún no se han regenerado.
