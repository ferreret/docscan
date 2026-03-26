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

    4 tipos de paso (imagen, barcode, OCR, script), 23+ operaciones de imagen, orden libre y configurable.

-   :material-barcode-scan:{ .lg .middle } **Reconocimiento**

    ---

    Doble motor de barcodes (14 simbologías), triple motor OCR, integración con Claude y GPT-4o.

-   :material-robot:{ .lg .middle } **AI Mode**

    ---

    Asistente conversacional para crear y configurar aplicaciones mediante lenguaje natural.

-   :material-language-python:{ .lg .middle } **Scripting Python**

    ---

    Motor de scripts con contexto completo, 7+ eventos del ciclo de vida, timeout configurable.

-   :material-export:{ .lg .middle } **Transferencia**

    ---

    Exportación a carpeta (TIFF, JPEG, PNG, PDF, PDF/A), transferencia avanzada por script, políticas de colisión.

</div>

## :rocket: Inicio rápido

```bash
# Clonar e instalar
git clone https://github.com/ferreret/docscan.git && cd docscan
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && alembic upgrade head

# Lanzar
python3.14 main.py
```

[Guía completa de inicio :material-arrow-right:](user-guide/getting-started.md){ .md-button .md-button--primary }

## :bar_chart: El proyecto en números

| Métrica | Valor |
|---------|-------|
| Líneas de código | **19.776** |
| Tests | **813 passing** :white_check_mark: |
| Operaciones de imagen | **23** |
| Simbologías de barcode | **14** |
| Motores OCR | **3** |
| Idiomas de interfaz | **3** (ES, EN, CAT) |

---

<p align="center">
  <sub>DocScan Studio v0.1 RC — © 2026 Tecnomedia</sub>
</p>
