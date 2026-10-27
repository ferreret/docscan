---
name: project-apps-arnau
description: "Réplica en DocScan de las Apps de FlexibarNET10 del Hospital Arnau de Vilanova — familia A hecha (lote 6), eCAP pendiente"
metadata:
  node_type: memory
  type: project
  originSessionId: 3a621b7a-a295-426c-a170-73582379252a
  modified: 2026-10-27T09:52:02.665Z
---

Desde el 2026-10-27, Nicolás quiere **replicar en DocScan las Apps que FlexibarNET10 tiene
desplegadas en el Hospital Arnau de Vilanova**. Es el caso de aceptación del lote 6
(separador de documento).

**Fuente de verdad:** `tools/SeedAppsArnau` del repo `Tecnomedia/FlexibarNET10`
(`ArnauApps.cs`, `ArnauScripts.cs`, `PaginasSinteticas.cs`), que a su vez porta 1:1 los XML
del Flexibar.NET legacy. Se clona con `gh repo clone Tecnomedia/FlexibarNET10 -- --depth=50`
en el scratchpad.

**Hecho (rama `feat/lote6-separadores`, PR #3, sin mergear; incluye grupo «Hospital Arnau de Vilanova», icono azul, twain + diálogo del escáner y descripción de «Data»):** las 6 Apps de archivo simple
(01, 02, 03, 05, 06, 07) en `tools/arnau_apps.py`; sembrador `tools/seed_apps_arnau.py`
(`--db`, `--export-base`, `--packs`, `--paginas`); smoke `tests/test_arnau_e2e.py` por el
worker real con códigos reales generados con zxing-cpp.

**Pendiente:** familia eCAP (04 y 08). Validan separador Code128 + contenido Code39
(NumICS) y registran pares (Pet, NumICS) en la tabla `PSM_SCANECAP` por ODBC **antes** de
archivar, con la cadena de conexión en un secreto de estación (`odbc_ecap`). En DocScan
faltan: secretos accesibles desde scripts y `pyodbc`. La BD del hospital no es accesible:
probar contra una base simulada.

**How to apply:** cualquier cambio en separadores, transferencia por documento o scripts de
nombre debe seguir pasando `tests/test_arnau_e2e.py`. Las descripciones de las Apps van en
catalán (las ve el operador); el campo de lote se llama «Data». Raíz de producción `W:\`.
Escaneos reales del hospital no se ceden (datos de pacientes): solo páginas sintéticas.

Relacionado: [[project_paridad_flexibarnet10]], [[next-session-resume]].
