---
hide:
  - navigation
---

# :page_facing_up: DocScan Studio

**Plataforma de captura, procesamiento e indexación de documentos con IA generativa**

<div class="grid cards" markdown>

-   :material-scanner:{ .lg .middle } **Captura**

    ---

    Escaneo directo via SANE (Linux) y TWAIN/WIA (Windows), importación por arrastrar y soltar, alimentador automático ADF.

-   :material-pipe:{ .lg .middle } **Pipeline composable**

    ---

    4 tipos de paso (imagen, barcode, OCR, script), 24 operaciones de imagen, orden libre y configurable.

-   :material-barcode-scan:{ .lg .middle } **Reconocimiento**

    ---

    Doble motor de barcodes (15 simbologías: 10 con el motor 1, las 15 con el motor 2), triple motor OCR y separador de documento por código de barras.

-   :material-robot:{ .lg .middle } **AI Mode**

    ---

    Asistente conversacional para crear y configurar aplicaciones mediante lenguaje natural, con Claude o GPT-4o.

-   :material-language-python:{ .lg .middle } **Scripting Python**

    ---

    Motor de scripts con contexto completo, 14 eventos del ciclo de vida y panel de verificación. Los pasos Script se cortan a los 30 s.

-   :material-export:{ .lg .middle } **Transferencia**

    ---

    Carpeta (TIFF, PNG, JPEG, PDF), PDF, PDF/A o TIFF multipágina por lote o por documento, CSV, nombre por patrón o por script, transferencia avanzada por script y políticas de colisión.

</div>

## :rocket: Inicio rápido

Descarga el instalador de la
[última versión](https://github.com/ferreret/docscan/releases/latest):

| Sistema | Fichero |
|---------|---------|
| Linux (x86_64) | `docscan-0.1.8-x86_64.AppImage`: dale permiso de ejecución y ábrelo |
| Windows | `docscan-0.1.8-setup.exe`: instalador |

Desde el código fuente (Python 3.14 con [uv](https://docs.astral.sh/uv/)):

```bash
git clone https://github.com/ferreret/docscan.git && cd docscan
uv venv --python 3.14 --managed-python
uv pip install -r requirements.txt
# Ubuntu: sudo apt install libzbar0t64 libsane-dev libxcb-cursor0

.venv/bin/python main.py
```

La base de datos se crea y se migra sola al arrancar.

[Guía completa de inicio :material-arrow-right:](user-guide/getting-started.md){ .md-button .md-button--primary }

## :sparkles: Novedades

**v0.1.8**: separador de documento nativo, con la lógica de FlexibarNET 10.

- El separador es una marca de la página (automática en el paso Barcode o a
  mano con `Ctrl+D`) y el **documento** es el tramo hasta el siguiente.
- Transferencia por documento: TIFF multipágina, un fichero por lote o por
  documento, página separadora como portada o descartada, tokens
  `{separator}`, `{document_index}` y `{document_id}`, y nombre por script.
- Reordenar páginas con `Alt+↑` / `Alt+↓`.
- Grupos de aplicaciones en el launcher, eventos que se pueden pausar y editor
  de scripts con colores.

**v0.1.7**: nada falla en silencio.

- Los campos de lote obligatorios y un `on_transfer_validate` que lanza
  bloquean la transferencia; un `on_transfer_advanced` que falla deja el lote
  sin exportar.
- Un script de pipeline que falla deja la página a revisión.
- El Workbench y el worker desatendido transfieren por el mismo camino.
- Interfaz rediseñada con la estética de FlexibarNET 10.

Detalle completo en el
[CHANGELOG](https://github.com/ferreret/docscan/blob/main/CHANGELOG.md).

## :bar_chart: El proyecto en números

| Métrica | Valor |
|---------|-------|
| Líneas de Python en `app/` | **27.407** |
| Tests | **1240 passing** :white_check_mark: |
| Cobertura de líneas | **72 %** |
| Operaciones de imagen | **24** |
| Simbologías de barcode | **15** |
| Motores OCR | **3** |
| Idiomas de interfaz | **3** (ES, EN, CAT) |

!!! note "Versión web archivada"
    La versión web SaaS está archivada y no se mantiene. Su documentación se
    conserva como referencia en la pestaña *Versión Web (archivada)*.

---

<p align="center">
  <sub>DocScan Studio v0.1.8 — © 2026 Tecnomedia</sub>
</p>
