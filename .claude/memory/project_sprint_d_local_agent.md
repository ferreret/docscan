---
name: Sprint D — Cliente local fase 2 (rama feature/local-agent-d)
description: Sprint en curso. Hito 13 frontend cerrado y parcialmente smoke-tested 2026-05-11 (HEAD da87822, 10 commits sobre feature/local-agent). Pendiente cerrar smoke + hitos 14-17.
type: project
originSessionId: 9d1f5f9d-0cbb-4de2-be2c-fca65c043f57
---
Sprint que cierra el cliente local como pieza apta para producción real, no sólo demo. Sin estos dos pilares no hay tag `v0.2.0`.

**Why:** el smoke real del hito 12 (sesión 2026-05-08 tarde, Canon DR-M160 USB) validó la cadena completa pair→escanear→pipeline→transferir, pero el operario destapó dos limitaciones que invalidan el MVP:

1. No hay diálogo de opciones de escaneo. Hoy `/scan-and-upload` y `/scan-adf-and-upload` aceptan sólo `scanner_name`+`batch_id`. La fuente, modo color, resolución, brillo, contraste, dúplex se quedan en defaults o lo que ImageConfig de la app ofrezca. El operario necesita poder elegirlas por escaneo (estilo `ScannerConfigDialog` del desktop).
2. "Transfer al cliente" es download, no script. El botón ↓ Local del hito 11 descarga el ZIP y lo extrae. Útil pero limitado. Lo que hace falta es ejecutar **scripts de transferencia en el cliente** con acceso al contexto enriquecido del pipeline (campos extraídos, OCR, barcodes, flags) para crear carpetas/nombres custom, unir PDFs, consultar/insertar en BD del cliente, llamar a APIs internas. Equivalente al modo `script` del `transfer_service` del desktop, llevado al cliente local.

**How to apply:** rama `feature/local-agent-d` arrancada 2026-05-08 desde `28f70c5`. HEAD `da87822` con **10 commits** sobre `feature/local-agent`. Plan detallado en `docs/superpowers/plans/2026-05-08-sprint-d-local-agent-plan.md`. Progresos en `docs/progreso_2026-05-08-sprint-d-inicio.md` (backend) y `docs/progreso_2026-05-11.md` (frontend).

## Decisión arquitectónica clave

Tras aclarar con el operario:

- **Windows (TWAIN/WIA)**: diálogo nativo del driver. Frontend NO renderiza nada — pasa `show_ui=true` al endpoint `/scan-*` y el agente lo propaga al desktop, que abre la ventana del driver en la sesión gráfica del operario.
- **Linux (SANE)**: diálogo dinámico construido por el frontend con `GET /scanners/{name}/options`. SANE es API C, no tiene UI propia; alternativa "lanzar xsane como subprocess" rompe el flujo del agente.
- **Flag `applications.scan_show_dialog: bool` (default true)** controla si se muestra ese diálogo o se escanea directo con la última config del escáner.

## Hito 13 — Backend cerrado 2026-05-08 (5 commits)

- `79912c4` — `GET /scanners/{name}/options` con cache TTL 60s + `?refresh=true`.
- `a750f78` — Overrides en `/scan-*` con whitelist dinámica.
- `3c3eb13` — `applications.scan_defaults_json TEXT NOT NULL DEFAULT '{}'` (migración `d4e8f6a9b132`).
- `a2acda5` — `supports_native_ui: bool` en `ScannerInfo`. Cambio breaking en frontend (store `string[]` → `AgentScanner[]`).
- `d552d1b` — `applications.scan_show_dialog: Boolean DEFAULT TRUE` (migración `e6f9a013c245`).

## Hito 13 — Frontend cerrado 2026-05-11 (4 commits)

- `a217763` — Composable `useScannerOptions` con cache de módulo + `refresh:true` invalida ambas capas. URL escapa solo caracteres problemáticos (mantiene `:` y `/` literales para path converter SANE). 9 tests TDD.
- `f09956a` — `ScannerOptionsDialog.vue` presentacional puro. Helper `inputKind()` clasifica: tupla numérica → range+number; lista enum → select; bool → checkbox. Secciones esenciales (intersección con `[resolution, mode, source, brightness, contrast]`) + avanzadas colapsable. Filtra `is_active=true` y `is_settable=true`. Patrón `aria-modal` y listener global de Esc del AddBarcodeDialog. 18 tests TDD. **Bug TDD detectado y corregido**: la 1ª implementación de `isTupleConstraint` clasificaba mal `[Color, Gray, Lineart]` como tupla por length=3 — ahora exige que los 3 elementos sean números.
- `79f2d83` — Integración en `ScanFromAgentMenu` con `decideStrategy()` y 4 ramas (native / dialog / direct / sin app=back-compat). `api/agent.ts::buildScanBody()` omite `options` y `show_ui` si no vienen → compat con agentes pre-hito-13. Cableado de prop `application` desde `WorkbenchView` → `WorkbenchToolbar` → menú. 12 tests TDD.
- `da87822` — Doc de progreso `docs/progreso_2026-05-11.md`.

## Tests al cierre 2026-05-11

| Suite          | Antes (2026-05-08) | Ahora | Delta |
|----------------|-------------------:|------:|-------|
| Desktop        | 869                | 869   | 0     |
| Backend web    | 340                | 340   | 0     |
| Agente local   | 127                | 127   | 0     |
| Frontend       | 507                | 546   | +39   |
| **Total**      | **1843**           | **1882** | **+39** |

Type-check `vue-tsc --noEmit` limpio.

## Smoke real Canon DR-M160 — sesión 2026-05-11 (parcial, retomar 2026-05-12)

Realizado hasta el paso 9 del plan. Verificaciones positivas:

- ✅ Stack docker + agente + dev server frontend funcionando juntos
- ✅ Login operario, "Mi estación" muestra agente vinculado + Canon detectada
- ✅ Toggle `scan_show_dialog` visible en configurador General (default true)
- ✅ Pulsar 🖨 ADF abre `ScannerOptionsDialog` (rama 'dialog' del `decideStrategy`)
- ✅ Dialog carga opciones reales del driver SANE de la Canon
- ✅ Cambiar mode → Lineart aplicado (log del agente: `mode=Lineart`)
- ✅ Subida al SaaS OK (`POST /api/batches/N/pages 201 Created` por cada hoja)
- ✅ Imágenes persistidas en MinIO con `image_path=2/<batch>/<hash>.png` correctos

Pendientes del smoke (retomar mañana):
- [ ] Persistencia `scan_defaults_json` tras "Recordar para esta aplicación"
- [ ] Recargar precarga los defaults guardados
- [ ] Rama `direct` (con `scan_show_dialog=false`)
- [ ] Rama `native_ui` (simulada con override del agente)
- [ ] Esc cierra dialog sin propagar al lote
- [ ] Click fuera cierra
- [ ] Atajos workbench bloqueados con dialog abierto
- [ ] JSON malformado tolerado

## Bug preexistente descubierto en el smoke (NO del hito 13)

`WorkbenchView` reutiliza la instancia del componente al navegar entre lotes (`/batches/5` → `/batches/6`). `batchId` es un `computed(route.params.id)`, pero la carga (fetchOne/fetchPages/fetchPage del primer page) sólo se hace en `onMounted` que no se ejecuta de nuevo. Síntoma: tras crear un lote nuevo desde uno abierto, el thumbnail panel y el viewer piden `/api/batches/<nuevo>/pages/<id-del-viejo>/image` y reciben 404 (correcto, cross-batch). **F5 lo arregla** porque resetea el state del store.

Fix sencillo: extraer la lógica del `onMounted` a una función `loadBatch(id)` y añadir `watch(batchId, loadBatch)`. O `<router-view :key="$route.params.id" />` para forzar re-mount.

Anotar como issue separada del hito 13 — no debe contaminar el smoke ni el commit final del sprint.

## Estado del entorno al cerrar la sesión 2026-05-11

Servicios corriendo en el equipo del operario (no detenidos):
- `docker compose` con api/worker/db/redis/minio levantados
- Agente local `python -m docscan_local_agent` en :47816
- Dev server frontend `npm run dev` en :5173

BD docker tras rebuild + migraciones:
- HEAD alembic: `e6f9a013c245`
- Tenant: TecnoMedia (id=2). NO existe SmokeTest (la BD se recreó respecto a la memoria vieja).
- Users: `superadmin@tecnomedia.es` (password desconocido), **`operario@tecnomedia.es` / `<REDACTADO — ver gestor de contraseñas>`** (reseteado en esta sesión).
- App: AppHito7 (id=2) con `scan_show_dialog=true`, `scan_defaults_json={}`.
- Lotes en BD: id 2-6 con 13 páginas totales. Lote más reciente (#6) tiene páginas 16, 17 ya escaneadas con dialog (mode=Lineart).
- Imágenes en MinIO bucket `docscan` con path `2/<batch>/<hash>.png`.

**Recuerda**: imagen `docscan-api` y `docscan-worker` fueron rebuild hoy a partir del código del hito 13. La imagen previa (de hace 2-3 días) NO tenía las migraciones del hito 13 y por eso el smoke inicial falló con "column scan_show_dialog does not exist". Si vuelves a ejecutar `docker compose up -d` sin tocar nada, las imágenes actuales son correctas.

## Frontend del hito 13 — recordatorio del scope ya cumplido

1. ✅ Composable `useScannerOptions(scannerName)` con cache local
2. ✅ `ScannerOptionsDialog.vue` con render dinámico
3. ✅ Integración en `ScanFromAgentMenu.vue` con 3 ramas + save-defaults
4. ⏳ Smoke real con Canon DR-M160 + doc del hito 13 (en curso, retomar 2026-05-12)

## Pilares e hitos previstos (resto del sprint)

### Pilar 1 — Opciones de escaneo dinámicas
- **Hito 13** (cierre en sesión 2026-05-12 tras smoke completo).

### Pilar 2 — Transfer scripts en cliente
- **Hito 14** (~1.5 sesiones): modo `local_script` en `transfer_json` + endpoint nuevo `POST /transfer-batch-script` en agente + ScriptEngine importado lazy + built-ins iniciales (`app, batch, pages, tmp_dir, log, http, re, json, Path, datetime` — sin acceso a la BD del SaaS) + editor CodeMirror en configurador web.
- **Hito 15** (~1 sesión): built-ins `db` (sqlite primero) y `pdf` (PyMuPDF wrapper).
- **Hito 16** (~0.5-1 sesión): snippets en el editor + smoke real (escanear con barcode, transfer_script crea `{año}/{barcode}/`).
- **Hito 17** (~0.5 sesión): smoke completo + tag v0.2.0 + doc MkDocs (`docs-web/local-agent-flow.md`).

## Tripwires del sprint

- Desktop: **869** tests verde tras cada hito.
- Web SaaS: **340** tests backend, **546+** frontend tras hito 13.
- Agente: **127** tests, crecen monotónicamente.
