# Ficha de DocScan Studio en el portfolio — paquete para actualizarla

Preparado el **2026-10-27**, tras publicar la **v0.1.8**. Es lo que necesita la
sesión del repo del portfolio para poner al día la ficha. Todo lo que hay aquí es
un **hecho con su fuente** o una **decisión ya tomada por Nicolás**; donde hace
falta que él decida, está marcado como **[A CONFIRMAR]**. Nada de este fichero es
texto final de la ficha: la redacción la hace la sesión del portfolio con sus
propias herramientas.

## 1. Qué hay que tocar en el portfolio

| Qué | Dónde |
|-----|-------|
| Ficha bilingüe | `~/Projects/Personal/portfolio/data/projects/docscan-studio.ts` (ya existe; `id: "4"`, `slug: "docscan-studio"`) |
| Captura | `docs/portfolio/docscan-studio.webp` de este repo → `public/` del portfolio |
| Flujo del portfolio | Su `CLAUDE.md`: el contenido es real y lo aporta Nicolás; `sync-bilingual` para el otro idioma; revisor `bilingual-content-reviewer` antes de commitear; `tsc --noEmit` como control |

**La imagen necesita un nombre nuevo.** El `nginx.conf` del portfolio sirve los
`.webp` (igual que los `.png`) con `Cache-Control: public, max-age=31536000,
immutable`. Si se reutiliza `docscan-studio.webp`, Cloudflare y los navegadores
seguirán enseñando la captura antigua durante un año. Hay que copiarla con otro nombre
(por ejemplo `public/docscan-studio-v018.webp`), cambiar `imageUrl` en las dos
lenguas y borrar la antigua.

## 2. Qué está mal en la ficha actual

| Campo | Dice | Realidad |
|-------|------|----------|
| `status` | `production` | **`in-development`**: hay releases con instaladores, pero ninguna instalación en producción (decisión de Nicolás, 2026-10-26) |
| `timeline` | «Released v0.1.0 — 2026-03-26» | Última versión **v0.1.8, 2026-10-27** |
| `description` | «…AI-powered field extraction…» | **No hay extracción de campos con IA.** La IA (Claude u OpenAI) se usa para *configurar*, en el AI Mode. El proceso de cada página es determinista (imagen, barcode, OCR, scripts) |
| `businessMetrics` | 849 tests, 19.776 líneas, 94 ficheros, v0.1.0 | Ver §4 |
| `problem` | Sistema legacy genérico, sin nombre | Se puede nombrar: FlexibarNET 10 de Tecnomedia, en hospitales (§3) |
| `lessonsLearned` | «absorbe el 90 % de los requisitos» | Sin prueba; decidido sustituir por lecciones con evidencia (§5) |
| `lessonsLearned` | «849 tests hicieron segura la subida a 3.14» | Cifra desfasada |
| Captura | Interfaz antigua, con un hospital real en un volante ficticio | Captura nueva con datos neutros (§7) |

## 3. Problema y solución: hechos

**Problema**

- **FlexibarNET 10** es el producto de captura documental de **Tecnomedia**, en .NET 10
  y WPF: **solo Windows**, con un SDK de imagen comercial con licencia.
- Está **en producción en hospitales**; su primera implantación hospitalaria real es
  el **Hospital Arnau de Vilanova** (escáneres Kodak).
  Fuente: `docs/propuestas_desde_flexibarnet10_2026-10-26.md` §1.
- Se puede nombrar Flexibar, Tecnomedia y sus implantaciones en hospitales, con
  nombres (decisión de Nicolás, 2026-10-26).

**Solución**

- DocScan Studio es su **reimplementación multiplataforma en Python** (Linux y
  Windows), con **paridad funcional** como requisito: misma lógica, mismas claves de
  configuración, mismos tokens; se sigue el manual de Flexibar cuando su código lo
  contradice, y las desviaciones solo con decisión explícita.
- Bibliotecas libres en lugar del SDK con licencia: OpenCV, pyzbar, zxing-cpp,
  PyMuPDF; escáner por SANE (Linux) y TWAIN/WIA (Windows).
- **Multi-aplicación**: N perfiles de proceso independientes (pipeline, campos,
  scripts, transferencia), agrupables en el launcher.
- **Pipeline composable**: imagen (24 operaciones), barcode (2 motores, hasta 15
  simbologías), OCR (3 motores) y scripts Python.
- **Separador de documento** por barcode, automático o manual, y **transferencia por
  documento** (PDF, PDF/A, TIFF multipágina) con nombre por patrón o por script.
- **IA generativa para configurar**: AI Mode crea, modifica, duplica o elimina
  aplicaciones completas en lenguaje natural con *tool calling*, y escribe el código
  de sus eventos; cada cambio se enseña antes de aplicarlo (aceptar / rechazar).
- Existe además un *Pipeline Assistant* en el código (`app/services/pipeline_assistant.py`,
  con su panel), pero **nunca se ha conectado a la interfaz**: no debe aparecer en la
  ficha como función disponible.
- **Worker desatendido** (carpeta vigilada) con el mismo flujo que la interfaz.
- Instaladores (AppImage, setup.exe) con actualización automática desde GitHub.

## 4. Métricas (medidas el 2026-10-27 sobre la v0.1.8)

Detalle y método en `docs/portfolio/metricas.md`. Formato de número: inglés
`27,407`, castellano `27.407`.

| Métrica | EN | ES |
|---------|----|----|
| Tests automáticos | 1,240 | 1.240 |
| Tests en fallo | 0 | 0 |
| Cobertura de líneas | 72% | 72 % |
| Versión publicada | v0.1.8 | v0.1.8 |
| Releases publicadas | 10 | 10 |
| Líneas de Python de la aplicación (`app/`) | 27,407 | 27.407 |
| Líneas de tests | 18,743 | 18.743 |
| Aplicaciones reales de FlexibarNET 10 portadas | 6 | 6 |
| Versiones de Flexibar analizadas (2.ª pasada) | 19 | 19 |
| Auditorías de Flexibar analizadas (2.ª pasada) | 6 | 6 |

Esquema acordado (2026-10-26): tests, versión, versiones de Flexibar analizadas y
**bugs hallados por smoke de extremo a extremo que los tests unitarios no veían**.
De estos últimos hay **tres** documentados en `c79e264`: el worker y `--direct-mode`
no recibían el servicio de barcodes (y el worker tampoco el de OCR) y se saltaban
esos pasos; el worker no guardaba los barcodes; y `on_transfer_validate` veía los
campos del intento anterior.

## 5. Lecciones con su prueba

El esquema de lecciones lo decidió Nicolás el 2026-10-26: cada una con su evidencia o
su número, en el estilo de la ficha del agente de recepción veterinaria.

1. **La paridad con un producto en producción es una especificación contra la que
   probar.** Seis aplicaciones reales del Hospital Arnau (archivo de peticiones,
   calidad y microbiología) portadas de FlexibarNET 10 con su misma configuración, y
   una prueba de extremo a extremo que las pasa por el worker real con códigos de
   barras reales. Fuente: `tools/arnau_apps.py`, `tests/test_arnau_e2e.py`, PR #3
   (`985bcad`).
2. **Un fallo tratado como éxito.** `run_event` devolvía `None` ante cualquier
   excepción y el worker lo traducía a éxito: si `on_transfer_advanced` lanzaba, el
   lote se marcaba como exportado; si fallaba `on_transfer_validate`, la validación
   dejaba pasar todo. Corregido con un flujo único que falla cerrado. Fuente:
   `docs/propuestas_desde_flexibarnet10_2026-10-26.md` §2, commit `c79e264`.
3. **El dato del papel no es de confianza.** Un barcode que empezaba por `/` (probado
   con `/tmp/evil` y el patrón `{first_barcode}`) escribía en esa ruta absoluta, fuera
   del destino. Ahora los valores se sanean y se comprueba que la ruta final queda
   dentro del destino. Fuente: mismo informe §2 (reproducido), `c79e264`.
4. **Los tests unitarios pasaban mientras el worker no leía ningún barcode.** Solo un
   smoke real del worker lo destapó (los tres bugs de §4). Fuente: `c79e264`.
5. **La documentación y los asistentes de IA se desvían del código.** Varias firmas
   de eventos documentadas no coincidían con lo que el código pasa a los scripts:
   `on_transfer_advanced` escrito según la documentación lanzaba `TypeError` y la
   transferencia se daba por buena; `init_global` no se ejecutaba nunca. Ahora un
   test impide que firmas y stubs diverjan. Fuente: commit `71c2650`.
6. **Las migraciones SQLite con recreación de tabla borraban datos.**
   `batch_alter_table` hace `DROP TABLE` y, con `PRAGMA foreign_keys=ON`, propagaba
   los `ON DELETE CASCADE`: medido sobre una base real, 8 lotes, 42 páginas y 58
   códigos quedaban en 0. Desde entonces cada release se prueba migrando una copia
   de una base real y comparando `COUNT(*)` (hecho también con la v0.1.8). Fuente:
   commit `82eeeb4`, `release: v0.1.8` (`0ba7fbb`).

Otra prueba disponible, por si se quiere: al portar las aplicaciones del Arnau,
guardar en Group4 una imagen que no era de 1 bit hacía caer libtiff; ahora un TIFF
usa Group4 solo si todas sus páginas son en blanco y negro, y LZW si no (como
Flexibar).

## 6. Resto de campos

| Campo | Valor |
|-------|-------|
| `status` | `in-development` |
| `role` | La ficha actual dice «Sole developer» / «Desarrollador único». **[A CONFIRMAR]** si sigue siendo así |
| `timeline` | Inicio 2026-03-07 (primer commit); v0.1.0 el 2026-03-26; v0.1.8 el 2026-10-27 |
| `link` / `repoUrl` | https://github.com/ferreret/docscan |
| `demoUrl` | No hay demo pública. El manual (https://ferreret.github.io/docscan/) o la última release (https://github.com/ferreret/docscan/releases/latest) pueden servir de enlace secundario. **[A CONFIRMAR]** |
| `tags` | Los actuales siguen siendo ciertos: Python, PySide6, OCR, IA generativa |
| `relatedPostId` | Opcional, un artículo de blog relacionado. **[A CONFIRMAR]** si hay uno |

**Stack** (sustituye al actual):

| Categoría | Elementos |
|-----------|-----------|
| UI | PySide6 (Qt 6), temas QSS |
| Lenguaje | Python 3.14 |
| Persistencia | SQLAlchemy 2.x, SQLite (WAL), Alembic |
| Códigos de barras | pyzbar + OpenCV, zxing-cpp |
| OCR | RapidOCR, EasyOCR, Tesseract |
| IA | Anthropic SDK, OpenAI SDK, *tool calling* (para configurar) |
| PDF | PyMuPDF (PDF/A) |
| Escáner | SANE (Linux), TWAIN + WIA (Windows) |
| Empaquetado | PyInstaller, AppImage, Inno Setup, actualización automática |
| Tests | pytest, pytest-qt |

## 7. Captura

- Fichero: `docs/portfolio/docscan-studio.webp` (1440 × 900, WebP calidad 85,
  59 KB). Generada con
  `tools/ui_snapshots.py --portfolio docs/portfolio/docscan-studio.webp`.
- Muestra el **Workbench** en tema oscuro con un lote de facturas ficticias de una
  empresa ficticia («Suministros Ejemplo S.L.»): la primera página es separadora de
  documento (zona naranja del panel derecho, con su valor), con sus códigos leídos,
  los campos de lote y el texto OCR. **Sin nombres de hospitales ni personas
  reales**, como se decidió.
- Texto alternativo propuesto: «Workbench de DocScan Studio con un lote de facturas
  separado en documentos por código de barras» / «DocScan Studio Workbench with a
  batch of invoices split into documents by barcode».
- Más capturas disponibles, con los mismos datos neutros: `docs/screenshots/`
  (launcher con grupos, configurador, AI Mode…).
