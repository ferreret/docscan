---
name: reference-dr-m160-sane
description: "Comportamiento real del Canon DR-M160 con SANE (canon_dr) en Ubuntu, medido el 2026-11-03: sin detección de fin de hoja, reversos negros en dúplex, opciones y trampas al probarlo."
metadata:
  node_type: memory
  type: reference
  originSessionId: 625922d9-4c71-4ce9-8707-f42e18cade5d
  modified: 2026-11-03T14:22:12.363Z
---

Canon DR-M160 en minis-nick-linux (Ubuntu 26.04), probado el 2026-11-03:

- USB `1083:163e` (Canon Electronics, **no** `04a9`). SANE: `canon_dr:libusb:BBB:DDD`
  (el número de dispositivo cambia al reconectar). Acceso sin sudo vía udev.
- Fuentes: `ADF Front | ADF Duplex`; modos `Lineart|Gray|Color`; 100–600 ppp.
  Valores por defecto del driver: Gray, 600 ppp y **tamaño Carta (279,4 mm)**.
- **No detecta el final de la hoja**: con altura máxima (355,554 mm) una A4 sale
  de 356 mm con franja de fondo. Hay que fijar `--page-width/--page-height` y `-x/-y`.
- **Dúplex: los reversos salen negros enteros** (media ~8/255) en cualquier altura.
  No es de DocScan (pasa con `scanimage` a pelo). Sin causa encontrada; no probado
  en Windows/TWAIN para descartar el hardware. Contadores: 7927 hojas, rodillo 4854.
- `scanimage -L | grep` falla en silencio: el backend `escl` de la HP DeskJet de red
  vuelca basura binaria y grep trata la salida como binaria. Usar `grep -a`.
- El `buffer-size 8000000` que avisa en `canon_dr.conf` es de otros modelos; inocuo.
- Para pruebas: la HP DeskJet 2700 (`HP_DeskJet_2700_series_09FF11`) imprime las
  hojas de `~/Projects/Personal/docscan-entornos/arnau/paginas/` con `lp -o media=A4 -o print-scaling=fit`.
  El DR-M160 alimenta desde abajo: cargar cara abajo con la hoja 1 abajo del todo.

Relacionado: [[next-session-resume]], [[project-apps-arnau]].
