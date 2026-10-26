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

**Pendiente, en este orden:**
- **E4a** — barra superior del Workbench: «Escanear» como botón primario, Importar y
  Procesar con icono, Transferir en verde y Cerrar lote en rojo, y fuera los radio
  buttons. Nicolás quiere ver antes cómo ha quedado lo hecho.
- **E4c** — tarjetas del launcher (icono y acento derivados de la configuración,
  etiquetas, menú ⋮) y barra de estado.
- **E4e/f** — panel derecho (barcodes como lista, campo de fecha) y lista de pasos del
  Configurador.
- Quedan colores literales en `app_list_widget.py` (las tarjetas, que se rehacen en
  E4c) y en `document_viewer.py` (la paleta de los recuadros de barcode sobre el papel,
  que se deja así a propósito).

**Herramienta:** las capturas offscreen de las ventanas reales se hacen con un script de
captura en el scratchpad (un `QApplication` con datos XDG aislados y `grab()` de
Launcher, Configurador y Workbench). La propuesta prevé llevarlo al repo como
`tools/ui_snapshots.py`.
