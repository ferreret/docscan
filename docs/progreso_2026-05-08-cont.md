# Progreso 2026-05-08 (continuación) — smoke real hito 12

## Resumen ejecutivo

Sesión vespertina dedicada al **smoke e2e con escáner físico** (hito 12
del sprint `feature/local-agent`). Se ejecutó la cadena completa
`pair → escanear ADF → pipeline → transferir al cliente` contra un
**Canon DR-M160** USB, escáner ADF-only de gama profesional. El smoke
pasó de extremo a extremo y, en el camino, destapó dos bugs y una
limitación operativa que no se ven con tests inline.

**Decisión de cierre del sprint**: el smoke valida el MVP del cliente
local pero también deja claro que el alcance acordado para v0.2.0 es
**insuficiente** para un cliente real. Se cierra el sprint sin tag y
se planifica un Sprint D con dos hitos grandes (opciones de escaneo
dinámicas + transfer scripts en el agente).

## Cadena verificada

```
Canon DR-M160 USB
  │
  ▼
sg scanner -c "scanimage -L"
  → device `canon_dr:libusb:001:010` is a CANON DR-M160 scanner
  │
  ▼
docscan_local_agent (localhost:47816, paired con tenant TecnoMedia)
  │
  ▼
POST /scan-adf-and-upload  scanner_name=canon_dr:libusb:001:010 batch_id=3
  → 4 hojas reales (peticiones del Hospital Universitario Virgen del Rocío)
  → cada hoja sube al SaaS vía POST /api/batches/3/pages (201)
  │
  ▼
Workbench muestra 4 thumbnails con vista previa
  │
  ▼
▶ Pipeline (vacío en AppHito7) → state=read, pipeline_processed=true en 4/4
  │
  ▼
↓ Local (LocalTransferDialog, modo "extracted", destino /tmp/docscan_smoke_local)
  → POST /transfer-batch en agente
  → GET /api/batches/3/export al SaaS con agent_token (200, ZIP de 28 MB)
  → unzip en /tmp/docscan_smoke_local/batch_3/
      ├── manifest.json
      └── pages/
          ├── page_0001.png  (PNG 2550x3300 RGB, 7.4 MB)
          ├── page_0002.png  (7.2 MB)
          ├── page_0003.png  (7.9 MB)
          └── page_0004.png  (7.2 MB)
```

Captura visual: `smoke_hito12_workbench_4pages.png`.

## Bugs encontrados y corregidos

### 1) SIGABRT del agente tras N llamadas a /scanners — libsane-pixma (commit 3b39350)

Tras 10-15 llamadas consecutivas a `GET /scanners` el proceso del
agente moría con `*** bit out of range 0 - FD_SETSIZE on fd_set ***:
terminated` y `Aborted`. Faulthandler ubicó el crash en
`libsane-pixma → sanei_bjnp_find_devices`, no en nuestro Canon (que
usa el backend `canon_dr`). El backend `pixma` enumera la red BJNP en
cada `sane.get_devices()` y acumula fds altos hasta superar
`FD_SETSIZE` (1024 por defecto en glibc) cuando ejecuta `FD_SET()` en
un `select()` interno. Bug de upstream conocido pero rara vez
visible en CLI porque `scanimage -L` se invoca una vez y muere.

**Fix**: cache TTL 60s en el endpoint `/scanners` del agente con
`?refresh=true` para forzar recálculo. El frontend usa `refresh=true`
sólo en el botón "Comprobar de nuevo". Stress de 50 GETs encadenados
ya no derriba el proceso.

No se tocó `app/services/scanner_service.py` — el desktop sigue
funcionando porque allí la lista se invoca puntualmente (al abrir el
diálogo de configuración del escáner), no en bucle.

Tests del agente: **11/11** (8 originales + 3 nuevos del cache:
`test_scanners_caches_between_calls`,
`test_scanners_refresh_true_bypasses_cache`,
`test_scanners_cache_not_populated_on_error`). Fixture autouse
`_reset_cache` limpia el state entre tests.

### 2) Frontend parseaba `string[]` en lugar del envelope del agente (commit 43db10e)

El store `agent.ts` hacía
`scanners.value = await agentFetch<string[]>('/scanners')` pero el
endpoint devuelve `{backend, scanners: [{name, backend}]}`. La UI de
"Mi estación" mostraba "No se ha detectado ningún escáner" aunque el
agente sí veía el Canon. **Los tests inline mockeaban un shape
ficticio**, lo cual nunca contradecía la implementación rota.

Es exactamente el patrón que la memoria del proyecto recoge bajo
"Tests inline pueden ocultar bugs reales — exigir smoke test e2e
contra transporte real antes de declarar 'validado'".

**Fix**: `loadScanners` ahora parsea el envelope real y mapea a
`string[]` para no tocar consumidores aguas abajo
(`ScanFromAgentMenu` sigue recibiendo `scanners[0]` como
`scanner_name`). Tests del store y de la vista ahora mockean el
shape correcto.

Tests del frontend: **14/14** (store + view).

## Limitación operativa: imagen docker-api desactualizada

El primer intento de transferencia local falló con 401 en
`GET /api/batches/3/export`. Causa raíz: la imagen `docscan-api:latest`
estaba construida el **2026-05-06**, antes de los hitos 7-11. El
endpoint `/export` no tenía aún el dependency `CurrentUserOrAgent` y
rechazaba el `agent_token`.

`docker compose build api worker` aplicó el código actual y la
transferencia funcionó al instante. **No es un bug de código**, pero
sí un recordatorio: cualquier despliegue del SaaS que no haga rebuild
tras los hitos 7-11 verá lo mismo.

→ Se añade nota en docs MkDocs en sesiones futuras (cuando se
documente el deploy del agente/SaaS).

## Limitaciones conocidas del MVP del cliente local

El smoke pasa pero el alcance del MVP **no llega a producción real**.
Dos huecos serios destapados durante la sesión:

### A) No hay diálogo de opciones de escaneo

Hoy `/scan-and-upload` y `/scan-adf-and-upload` aceptan sólo
`scanner_name` y `batch_id`. La fuente (`ADF Front` / `ADF Duplex` /
`Flatbed`), modo color (`Lineart` / `Gray` / `Color`), resolución
(100-600 dpi), brillo, contraste, dúplex, etc. quedan en valores por
defecto. Para producción real el operario necesita poder elegir esas
opciones por escaneo (estilo el `ScannerConfigDialog` del desktop).

### B) "Transferir al cliente" es download, no script

El botón **↓ Local** del hito 11 descarga el ZIP del lote y lo
extrae en una carpeta. Útil pero limitado. Lo que se necesita en
realidad es ejecutar **scripts de transferencia en el cliente** con
acceso al contexto enriquecido del pipeline (campos extraídos, OCR,
barcodes, flags…) para hacer cosas como:

- Crear carpetas según los `page.fields` o el contenido de barcodes.
- Renombrar/numerar ficheros con plantillas (`{nuhsa}_{fecha}.pdf`).
- Unir páginas en un único PDF/A.
- Consultar bases de datos del cliente para obtener metadata adicional.
- Insertar registros en sistemas locales (BD, ERP, gestor documental
  on-prem, etc.).
- Llamar a APIs internas del cliente que no son accesibles desde el SaaS.

Esto es el equivalente al modo `script` del `transfer_service` del
desktop, llevado al cliente local. Convierte al agente de "puente USB
+ descargador" en "mini-runner de scripts del cliente con contexto
del pipeline" — un cambio de naturaleza, no un retoque.

## Cierre del sprint

- **`feature/local-agent`** queda en HEAD `43db10e`, **13 commits**
  sobre `main`. 11 hitos cerrados (0-11) + smoke parcial del hito 12
  con bugs encontrados y arreglados. **Sin tag** — la pieza no está
  lista para v0.2.0.
- Los dos huecos de arriba son trabajo serio. Pasan a un **Sprint D**
  con dos hitos grandes:
  - **Hito 13 — Opciones de escaneo dinámicas**: 1 sesión.
    `GET /scanners/{name}/options` en el agente, `ScannerOptionsDialog`
    en el frontend que se abre al pulsar 🖨, persistencia de defaults
    por aplicación.
  - **Hitos 14-16 — Transfer scripts en cliente**: 3-4 sesiones.
    El agente importa `ScriptEngine`, modo `local_script` en
    `transfer_json`, editor de scripts de transferencia en el
    configurador web, smoke real que demuestre creación de carpetas
    custom + plantillas de nombre + (opcional) inserción en BD del
    cliente.

Plan detallado pendiente en
`docs/superpowers/plans/2026-05-08-sprint-d-plan.md` (siguiente bloque
de la sesión).

## Tests al cierre

| Suite             | Antes  | Ahora  | Delta            |
|-------------------|--------|--------|------------------|
| Desktop puro      | 869    | 869    | sin cambios      |
| Backend web       | 336    | 336    | sin cambios      |
| Agente local      | 105    | 108    | +3 (cache scanner)|
| Frontend web      | 505    | 505    | sin cambios       |

Total proyecto: **1818 passing, 0 failed**.

## Archivos tocados

- `docscan_local_agent/routers/scanners.py` — cache TTL + `?refresh`.
- `docscan_local_agent/tests/test_scanners.py` — fixture autouse + 3 tests.
- `web/frontend/src/stores/agent.ts` — parseo del envelope + flag refresh.
- `web/frontend/src/views/MiEstacionView.vue` — usa `loadScanners(true)` en
  el botón "Comprobar de nuevo".
- `web/frontend/tests/stores/agent.store.test.ts` — mock del shape real.
- `web/frontend/tests/views/MiEstacionView.test.ts` — idem.
