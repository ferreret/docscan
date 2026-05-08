# Progreso 2026-05-08 (Sprint D — inicio del hito 13)

## Resumen ejecutivo

Tercera sesión del día. Tras cerrar el sprint anterior (`feature/local-agent`)
con el smoke real y dos bugs corregidos, se abrió el **Sprint D** con el
objetivo de cerrar el cliente local como pieza apta para producción.

Esta sesión cubre **el backend completo del hito 13** (opciones de escaneo
dinámicas) sobre la rama nueva `feature/local-agent-d`. El frontend del
hito 13 (composable + diálogo dinámico + integración en `ScanFromAgentMenu`)
queda pendiente para la próxima sesión.

## Decisión arquitectónica clave de la sesión

Tras ronda de aclaraciones con el operador, la dirección final del diálogo
de opciones de escaneo es:

- **Windows con TWAIN/WIA** → diálogo nativo del driver del fabricante.
  El frontend NO renderiza nada. El agente recibe `show_ui=true` y el
  driver pinta su propio diálogo en la sesión de escritorio del operario.
- **Linux con SANE** → diálogo dinámico construido por el frontend a
  partir de `GET /scanners/{name}/options`. SANE es API C sin UI propia,
  así que esto es lo único viable que mantiene el flujo coherente con
  el agente (alternativa "lanzar xsane como subprocess" rompía el agente).
- **Flag por aplicación `scan_show_dialog: bool`** que decide si se
  muestra el diálogo o se escanea directo con la última configuración
  del escáner. Default `true`.

## Cambios cerrados (5 commits sobre `28f70c5`)

### `79912c4` — `GET /scanners/{name}/options`

Endpoint nuevo en el agente que delega en `scanner.get_device_options(source)`
(método ya existente en el desktop sin tocar). Devuelve
`list[DeviceOptionInfo]` con `name/title/description/type/unit/constraint/value/is_active/is_settable`.

Cache TTL 60 s indexado por scanner_name con `?refresh=true` para
invalidar — mismo workaround del segfault de libsane-pixma que aplicamos
al `/scanners` general. Validación previa: si el `scanner_name` no está
en `list_sources()`, 404 limpio sin abrir el USB.

`DeviceOptionInfo` replica el dataclass del desktop pero como
`pydantic.BaseModel` para no importar el namespace `app/` desde
`docscan_local_agent` (mantiene el agente desacoplado para PyInstaller).
Pydantic v2 acepta tanto el dataclass original como un `dict` con la
misma forma vía `model_validate(..., from_attributes=True)`.

**Tests**: 11 base + 9 nuevos (happy, 401, 404, 503, 500 si revienta
`get_device_options`, cache hit/miss, `?refresh=true`, cache-por-scanner,
close en happy path). Fixture autouse `_reset_cache` ahora invalida
también el cache de options entre tests.

### `a750f78` — Overrides dinámicos en `/scan-*` con whitelist

`POST /scan-and-upload` y `POST /scan-adf-and-upload` aceptan un campo
opcional `options: dict` con overrides del dispositivo (resolution, mode,
source, brightness, contrast, ...). El agente:

1. Consulta `scanner.get_device_options(scanner_name)` para construir
   la whitelist dinámica de claves `is_settable=True`.
2. Rechaza con 422 cualquier clave fuera de la whitelist o no
   modificable. **El acquire NO se dispara si la validación falla**
   (importante en `/scan-adf-and-upload` para evitar abrir el stream
   y luego emitir el 422 dentro de NDJSON).
3. Inyecta el dict en `ScanConfig.extra_options`, que `acquire`/
   `acquire_iter` ya consumen desde el desktop sin cambios. Los campos
   top-level `resolution`/`mode` se conservan por compat (hito 7) y se
   ignoran si vienen overrides explícitos.

Helper `_validate_options_whitelist(scanner, name, options)` en
`scan_upload.py`, reutilizado desde `scan_adf.py`.

**Bug preexistente arreglado de paso**: la fixture `client` de
`conftest.py::tests` no aislaba `~/.docscan/`. Cuando había un agente
pareado en la máquina (caso típico tras el smoke), `test_status` rompía.
Ahora la fixture overridea `get_settings` con un `tmp_path` por defecto.

**Tests**: 124 base + 7 nuevos del override → **125/125** verde en agente.
Desktop scanner_service intacto (12/12 verde).

### `3c3eb13` — `applications.scan_defaults_json`

Persiste los defaults del diálogo de opciones por aplicación. El
frontend los precarga al abrir el `ScannerOptionsDialog` para evitar
que el operario reconfigure cada vez. **El agente NO consulta este
campo** — recibe los overrides directamente del frontend en cada
llamada a `/scan-*` (mantiene la separación agente/SaaS).

Migración Alembic `d4e8f6a9b132` con `op.batch_alter_table` y
`server_default='{}'` (compat SQLite + Postgres). Modelo y schemas
añaden el campo. El router PATCH ya hace `setattr(app, key, value)`
en bucle, así que no necesita cambios en `applications.py`.

**Tests**: backend **1207/1207** verde tras la migración (+2 nuevos
en `TestApplicationsCRUD`: default `'{}'` y persistencia vía PATCH).

### `a2acda5` — `supports_native_ui` en `/scanners`

Cada `ScannerInfo` reporta ahora `supports_native_ui: bool`. Lectura
desde `getattr(scanner, "supports_native_ui", False)` — la property ya
existe en `BaseScanner`, sólo `TwainScanner`/`WiaScanner` la
sobreescriben a `True`.

**Cambio breaking en frontend** (recogido y verificado): el state
del store agent pasa de `scanners: string[]` a `AgentScanner[]`.
Helper computed `scannerNames` para consumidores que sólo necesitan
nombres y método `findScanner(name)` para localizar un scanner por
nombre. `MiEstacionView` y `ScanFromAgentMenu` actualizados.

**Tests**: agente 127/127 (+2 native_ui), frontend 506/506 (+1 del
`findScanner`).

### `d552d1b` — `applications.scan_show_dialog` (default `true`)

Flag por aplicación que decide la UX del workbench al pulsar 🖨:

- `true` (default): muestra diálogo (TWAIN nativo en Windows, dialog
  dinámico en Linux con datos reales del driver SANE).
- `false`: escáner usa última configuración, captura directo.

Migración Alembic `e6f9a013c245` con `Boolean DEFAULT TRUE`. Frontend:
toggle nuevo en la pestaña "General" del configurador con nota
explicativa que cubre los dos sistemas operativos. Estado local
(`current`/`original`) y `configFromApp` lo cargan/persisten.

**Tests**: backend 13/13 CRUD (+2 nuevos default+patch), frontend
**507/507** (+1 nuevo del checkbox y persistencia).

## Estado al cierre

Rama `feature/local-agent-d` con **5 commits** sobre `feature/local-agent`
(que a su vez tenía 13 sobre `main`). Total **18 commits** sobre `main`.

| Suite               | Antes (sprint anterior) | Ahora (cierre sesión) | Delta |
|---------------------|------------------------:|-----------------------:|-------|
| Desktop puro        | 869                     | 869                    | 0     |
| Backend web         | 336                     | 340                    | +4    |
| Agente local        | 108                     | 127                    | +19   |
| Frontend web        | 505                     | 507                    | +2    |
| **Total**           | **1818**                | **1843**               | +25   |

## Pendiente de la sesión

Frontend del diálogo dinámico (Linux/SANE) en cuatro piezas:

1. **Composable `useScannerOptions(scannerName)`** — fetch a
   `GET /scanners/{name}/options` con cache local en Pinia.
2. **`ScannerOptionsDialog.vue`** — render dinámico con sección
   "Esenciales" (resolución/modo/fuente/brillo/contraste) y "Avanzadas"
   colapsable. Combo si `constraint` es lista, slider/range si es tupla
   `(min, max, step)`, checkbox si es bool. Botón "Recordar para esta
   aplicación" hace `PATCH /api/applications/{id}` con
   `scan_defaults_json` actualizado.
3. **Integración en `ScanFromAgentMenu.vue`** — al pulsar 🖨:
   - Si `scanner.supports_native_ui` → manda `show_ui=true` al endpoint
     `/scan-*` y el driver TWAIN/WIA pinta su propio diálogo.
   - Si no y `app.scan_show_dialog` → abre `ScannerOptionsDialog`,
     espera respuesta y dispara `/scan-*` con `options=` los overrides
     elegidos.
   - Si no y `!app.scan_show_dialog` → dispara `/scan-*` directo sin
     `options`, el driver SANE/TWAIN usa su última configuración.
4. **Smoke real** con Canon DR-M160 + doc del hito 13. Si todo OK,
   continuar con hitos 14-16 (transfer scripts) en sesiones siguientes.

## Plan del Sprint D (recordatorio)

`docs/superpowers/plans/2026-05-08-sprint-d-local-agent-plan.md`. 5
hitos restantes (13 a 17). El 13 es el más acotado (1 sesión), los
14-16 son los grandes (transfer scripts en cliente con built-ins
http/db/pdf), el 17 cierra con tag `v0.2.0`.

## Archivos clave

Backend agente:

- `docscan_local_agent/routers/scanners.py` — endpoint nuevo
  `/scanners/{name}/options` + cache TTL + `DeviceOptionInfo`.
- `docscan_local_agent/routers/scan_upload.py` — campo `options`,
  helper `_validate_options_whitelist`, override.
- `docscan_local_agent/routers/scan_adf.py` — mismo, reutilizando el
  helper.
- `docscan_local_agent/tests/conftest.py` — fixture `client` aísla
  ahora `~/.docscan/` con `tmp_path` (bug preexistente).
- `docscan_local_agent/tests/test_scanners.py` — +9 tests del options
  endpoint + 2 del `supports_native_ui`.
- `docscan_local_agent/tests/test_scan_upload.py`,
  `test_scan_adf_upload.py` — +7 tests del override + whitelist.

Backend SaaS:

- `alembic/versions/d4e8f6a9b132_add_scan_defaults_to_applications.py`.
- `alembic/versions/e6f9a013c245_add_scan_show_dialog_to_applications.py`.
- `app/models/application.py` — `scan_defaults_json` y `scan_show_dialog`.
- `web/api/schemas/application.py` — schemas `_ApplicationBase` y
  `ApplicationUpdate`.
- `tests/test_web_api.py` — +4 tests CRUD del campo.

Frontend:

- `web/frontend/src/api/types.ts` — `AgentScanner`, `DeviceOptionInfo`,
  `ScannerOptionsResponse`, `scan_defaults_json`, `scan_show_dialog`.
- `web/frontend/src/stores/agent.ts` — state objetos, `scannerNames`,
  `findScanner`.
- `web/frontend/src/views/applications/GeneralConfigEditorView.vue` —
  toggle `scan_show_dialog`.
- `web/frontend/src/views/MiEstacionView.vue`,
  `web/frontend/src/components/workbench/ScanFromAgentMenu.vue` —
  adaptados al nuevo shape.
- Tests del store, view y configurador actualizados.
