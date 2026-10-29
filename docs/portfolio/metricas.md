# Métricas de DocScan Studio — v0.1.9

Medidas el **2026-10-29** sobre el tag de la release **v0.1.9** (commit `4e2344d`),
en Linux (Ubuntu 26.04, Python 3.14.8). Son las cifras que usan el README, el
informe del proyecto y la ficha del portfolio: si se vuelven a medir, se cambian
aquí y en esos tres sitios a la vez.

## Cifras

| Métrica | Valor | Cómo se midió |
|---|---|---|
| Versión publicada | **v0.1.9** (2026-10-27) | `gh release list` |
| Releases publicadas | **12** (v0.1.0 a v0.1.9, más dos candidatas de v0.1.0) | `gh release list` |
| Primera versión | v0.1.0, 2026-03-26 | `gh release list` |
| Inicio del proyecto | 2026-03-07 (primer commit) | `git log --reverse` |
| Commits | **502** | `git rev-list --count HEAD` |
| Tests automáticos (escritorio) | **1226**, 0 fallos | `pytest tests/ -q` (offscreen, ~38 s) |
| Cobertura de líneas | **75 %** de `app/` + `docscan_worker/` | `pytest --cov=app --cov=docscan_worker` |
| Líneas de Python en `app/` | **26.172** (20.796 sin blancos ni comentarios) | `wc -l` / `grep -cvE '^\s*(#\|$)'` |
| Ficheros Python de la aplicación | **118** (`app/`, `config/`, `main.py`) | `find … -name '*.py'` |
| Líneas de tests de escritorio | **18.375** (14.355 sin blancos ni comentarios) | ídem sobre `tests/`, sin los de la web archivada |
| Ficheros de test de escritorio | **50** | ídem |
| Apps de FlexibarNET10 portadas | **6** (archivo simple del Hospital Arnau de Vilanova) | `tools/arnau_apps.py` |

Los tests de la web SaaS archivada (10 ficheros `test_web_*`, `test_arq_*` y
`test_pipeline_runner_events`) no cuentan: se omiten solos sin sus dependencias.

## Paridad con FlexibarNET10

Cifras del análisis de la segunda pasada
(`docs/propuestas_desde_flexibarnet10_2026-10-26.md`):

- **19 versiones** de Flexibar revisadas (v1.11.1 → v1.30.0) y **6 auditorías**,
  además de la primera de julio contra v1.11.0.
- Cada hallazgo de «DocScan tiene el problema» está comprobado con fichero:línea; los
  dos más graves, reproducidos.

## Cifras anteriores, ya desfasadas

Para reconocerlas si aparecen en algún sitio: en la v0.1.8 (2026-10-27) eran 1240
tests, 72 % de cobertura, 27.407 líneas en `app/` y 481 commits; bajan en la v0.1.9
porque se retiró el Pipeline Assistant con sus 30 tests. Antes, el README decía 939 tests y 22.425
líneas; la ficha del portfolio, 849 tests, 19.776 líneas y v0.1.0. Se midieron en
otros momentos y no está claro con qué criterio de líneas.
