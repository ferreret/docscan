---
name: Sprint cliente local web (rama feature/local-agent — CERRADO)
description: Sprint cerrado 2026-05-08 con smoke real (Canon DR-M160). Sin tag v0.2.0 — gaps de scope a Sprint D.
type: project
originSessionId: 17b67523-1d7a-472d-acd4-febc626d0e63
---
Sprint para que la web SaaS pueda escanear desde el PC del operario sin que el navegador cargue con el binario del escáner. El agente local es un FastAPI ligero (`docscan_local_agent/`) que importa `app.services.scanner_service` del desktop sin modificarlo y se empaqueta con PyInstaller.

**Why:** la versión web SaaS no tiene acceso a hardware local y el plan de portfolio cloud-first descarta SANE/TWAIN en el servidor. El agente cierra ese gap manteniendo la restricción dura "no romper desktop" (869 tests desktop intactos cada hito tras añadir el contrato `acquire_iter`).

**How to apply:** la rama es `feature/local-agent` cerrada en HEAD `28f70c5` (15 commits sobre main, sesión 2026-05-08 tarde). Sprint cerrado **sin tag v0.2.0** porque el smoke destapó dos huecos de scope: ver `project_sprint_d_local_agent.md` para el plan del siguiente sprint. Detalle de la sesión final en `docs/progreso_2026-05-08-cont.md`.

## Estado al cerrar 2026-05-08 (hito 9)

- **Sesión A (hitos 0-3) cerrada** — baseline + esqueleto FastAPI + tabla `agent_devices` + 4 endpoints `/api/agent/*` (pair-init, pair-claim, whoami, heartbeat).
- **Sesión B (hitos 4-7) cerrada** — pairing en agente con `agent.json` 0600, `GET /scanners` delegando en scanner_service, `POST /scan` single-page (PNG raw), dependency híbrida user+agent en SaaS, `POST /scan-and-upload` que cierra la cadena.
- **Sesión C 2026-05-08, hito 8 cerrado** — `POST /scan-adf-and-upload` con `StreamingResponse` NDJSON. Refactor aditivo en `scanner_service`: `BaseScanner.acquire_iter` (default delega en `acquire`), `SaneScanner.acquire_iter` con generator real. Twain/Wia heredan default. Decisión: NO chequea `is_disconnected` (deliberado, conservar páginas ya capturadas).
- **Sesión C 2026-05-08, hito 9 cerrado** — CORS amplio en el agente (`allow_origins=*`, `allow_credentials=False`). Vista `MiEstacionView.vue` con 3 estados (sin agente / sin vincular / vinculado), store Pinia `agent.ts` con `detect/pair/loadScanners`, ruta `/mi-estacion` y entrada en sidebar. Pairing one-click: el frontend encadena `pair-init` SaaS → `pair` agente sin que el operario copie códigos.
- **Sesión C 2026-05-08, hito 10 cerrado** — botones "🖨 Flatbed" y "🖨 ADF" integrados en el `WorkbenchToolbar` vía componente `ScanFromAgentMenu.vue`. Helpers en `web/frontend/src/api/agent.ts` (`scanFlatbed` POST simple, `scanAdf` async generator que parsea NDJSON con `body.getReader()` + buffer + decoder). Banner de progreso en el WorkbenchView con contador de páginas; `store.fetchOne` por cada `page_uploaded` para refresco en tiempo real. Componente oculto si el agente no está disponible/vinculado/sin scanners. Flujo end-to-end del cliente local cerrado.
- **Sesión C 2026-05-08, hito 11 cerrado** — transferencia local. `GET /api/batches/{id}/export` ampliado a `CurrentUserOrAgent` (cambio mínimo, mismo aislamiento multi-tenant). Endpoint nuevo en agente `POST /transfer-batch` con modos `extracted` (default, extrae ZIP en `{destination}/batch_{id}/`) y `zip` (escribe ZIP tal cual). `saas_client.download_batch_export(batch_id, agent_token)`. Frontend: helper `transferBatchToLocal()`, `LocalTransferDialog.vue` (input destino + radio modo), botón "↓ Local" en toolbar (visible solo si agente vinculado y lote con páginas). Defensa contra zip-slip al extraer. Cierra el caso "servidor remoto sin acceso a la red del cliente".

## Tripwires (cumplidos cada hito)
- Desktop puro: **869** (era 865, +4 `TestAcquireIterContract` con `_FakeScanner` que no requiere SANE/TWAIN/WIA).
- Backend web: **336** (320 base + 13 hito 7 + 3 `TestExportBatchAgent` hito 11).
- Tests del agente: **105** en `docscan_local_agent/tests/` (79 base + 11 hito 8 + 4 CORS hito 9 + 11 transfer-batch hito 11). Separados, no entran en tripwires del repo principal.
- Frontend: **505** (461 base, +9 store agent + 5 vista MiEstacion hito 9, +9 api/agent + 11 ScanFromAgentMenu hito 10, +3 helper transferBatchToLocal + 7 LocalTransferDialog hito 11).

## Endpoints disponibles
- **SaaS**: los 4 de hito 3 + `POST /api/batches/{id}/pages` (hito 7) y `GET /api/batches/{id}/export` (hito 11) aceptan JWT user **o** agent_token.
- **Agente** (`http://127.0.0.1:47816`, todos detrás de CORS hito 9): `GET /status`, `POST /pair`, `GET /scanners`, `POST /scan`, `POST /scan-and-upload`, `POST /scan-adf-and-upload`, `POST /transfer-batch` (hito 11).

## Frontend (hito 9)
- Store `web/frontend/src/stores/agent.ts` — `detect/pair/loadScanners/reset`. Llamadas al SaaS vía `api.post`, llamadas al agente vía `fetch` directo a `127.0.0.1:47816`.
- Vista `web/frontend/src/views/MiEstacionView.vue` — 3 estados render-condicional según `available`/`paired`. Pairing one-click: input nombre del equipo + botón "Vincular este equipo" ejecuta `pair-init` SaaS → `pair` agente → `detect` sin copy-paste.
- Ruta `/mi-estacion` (auth:true, sin role guard — visible a todos los roles). Entrada en sidebar entre Lotes y Equipo.

## Decisiones arquitectónicas clave
- **Token formato `{device_id}.{secret}`** — verificación O(1) con bcrypt, sin barrido de toda la tabla.
- **Réplica de schemas en agente** (`saas_schemas.py`) — el agente NO importa `web.api.*` para no arrastrar SQLAlchemy/alembic al PyInstaller.
- **Lazy import de scanner_service** — el agente arranca aunque falten SANE/TWAIN; sólo `/scanners` y `/scan` fallan con 503.
- **PNG raw en `/scan`** (no base64) — Blob estándar para el frontend, 33 % menos overhead.
- **Agente sube directamente al SaaS** en `/scan-and-upload` — evita el doble salto navegador→agente→navegador→SaaS, prerequisito para el ADF streaming del hito 8.
- **agent.json con permisos 0600 + escritura atómica** (`tmp + os.replace`) — el `agent_token` es credencial long-lived; un fallo a media escritura no deja JSON corrupto.
- **NDJSON sobre WS/SSE para el ADF streaming** — estándar HTTP plano, consumible con `fetch().body.getReader()`. Sin canal de vuelta no hace falta WS; SSE añade ceremonia (`text/event-stream`, reconnect handshake) innecesaria.
- **Refactor aditivo de `scanner_service`** — `BaseScanner.acquire_iter` con default que delega en `acquire`. Subclases sin streaming real (Twain/Wia, sin hardware Windows en la máquina dev) cumplen el contrato sin cambios.
- **NO `is_disconnected` en `/scan-adf-and-upload`** — si el cliente cierra a media cinta el bucle agota el ADF y las páginas siguen subiendo al SaaS. Perder páginas físicas ya capturadas sería peor UX que un cliente sin últimos eventos.
- **CORS amplio en el agente con `allow_credentials=False`** — el agente sólo escucha en `127.0.0.1` y la auth interna es por presencia de `agent.json` (no cookies). Cerrar credentials anula CSRF desde una web maliciosa.
- **Pairing one-click sin copy-paste de códigos** — el frontend encadena `pair-init` SaaS → `pair` agente automáticamente. El código existe pero el operario no lo ve.
- **Hito 9 sin botones "Escanear"** — la captura sube al SaaS contra un `batch_id` y eso lo hace el workbench (hito 10), no la vista "Mi estación" que es global.

## Bugs documentados
- **FastAPI + `from __future__ import annotations`**: si `CurrentUserOrAgent` (alias `Annotated[Principal, Depends(...)]`) se importa **dentro** de un fixture, `get_type_hints()` no lo encuentra al resolver la firma del handler dummy y FastAPI trata el parámetro como query → 422 "Field required" en lugar de 401. Fix: import a nivel módulo. Adicional: rutas añadidas tras `TestClient.__enter__()` también pierden parte de la resolución; los endpoints de test se montan en fixture pre-TestClient.

## Sesión 2026-05-08 (tarde) — smoke real hito 12 + cierre del sprint

- **Hardware**: Canon DR-M160 USB (`canon_dr:libusb:001:010`), ADF-only, sin flatbed. Backend `canon_dr` de SANE.
- **Cadena completa verificada**: pair → escanear ADF (4 hojas Hospital Universitario Virgen del Rocío, ~3.5s/hoja a 300 dpi color) → pipeline (vacío en AppHito7 → state=read) → ↓ Local (LocalTransferDialog modo extracted) → 4 PNG 2550x3300 + manifest.json en disco.
- **Bug 1 corregido (commit 3b39350)**: SIGABRT del agente tras 10-15 GET /scanners. Faulthandler ubicó el crash en `libsane-pixma → sanei_bjnp_find_devices` acumulando fds altos hasta `FD_SETSIZE on fd_set`. Bug del backend `pixma` (escaneo BJNP de red), no del Canon. **Fix**: cache TTL 60s en `/scanners` con `?refresh=true` para invalidar. Stress de 50 GETs ya no derriba el proceso. **NO se tocó scanner_service.py** (desktop puro intacto). Tests 11/11 verde con fixture autouse `_reset_cache`.
- **Bug 2 corregido (commit 43db10e)**: store frontend parseaba `string[]` cuando el agente devuelve `{backend, scanners: [{name, backend}]}`. Tests inline mockeaban shape ficticio. Patrón típico de "tests inline pueden ocultar bugs reales". Fix: `data.scanners.map(s => s.name)`. Tests 14/14 verde.
- **Limitación operativa**: imagen `docscan-api:latest` era del 2026-05-06 (anterior a hitos 7-11). El endpoint `/api/batches/{id}/export` no tenía `CurrentUserOrAgent` → 401 al agente. `docker compose build api worker` lo arregló. **No es bug de código** pero hay que documentar el "rebuild tras hitos 7-11" en deploy docs.
- **Decisión clave del cierre**: NO tag v0.2.0. El smoke validó la cadena pero el operario destapó dos gaps que invalidan el MVP como pieza de producción: (1) no hay diálogo de opciones de escaneo (modo, resolución, fuente), (2) "transfer local" es download, no script con contexto del pipeline. Plan del Sprint D en `docs/superpowers/plans/2026-05-08-sprint-d-local-agent-plan.md` y memoria en `project_sprint_d_local_agent.md`.

## Tests al cierre del sprint
- Desktop: **869**, sin cambios.
- Backend web: **336**, sin cambios.
- Agente: **108** (105 + 3 nuevos del cache).
- Frontend: **505**, sin cambios.
- Total: **1818 passing, 0 failed**.

## Datos en BD docker tras el smoke (volumen persistente)
- Tenant TecnoMedia (id=2, plan enterprise).
- Users: `superadmin@tecnomedia.es` (id=11, superadmin), `operario@tecnomedia.es` (id=14, operator, password `<REDACTADO — ver gestor de contraseñas>` — creado para el smoke).
- App AppHito7 (id=2, pipeline vacío).
- Batches: #2 (1 página, state=created), #3 (4 páginas escaneadas con ADF, state=read).
- AgentDevices: #4 (Smoke H7), #5 (PC-Smoke-Hito12, paired al usuario operario).

## Próxima sesión: Sprint D
Crear rama `feature/local-agent-d` desde `28f70c5`. Empezar por **Hito 13** (opciones de escaneo dinámicas, ~1 sesión, el más acotado). Plan completo en `docs/superpowers/plans/2026-05-08-sprint-d-local-agent-plan.md`.
