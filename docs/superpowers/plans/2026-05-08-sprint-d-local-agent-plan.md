# Sprint D — Cliente local fase 2 (opciones de escaneo + transfer scripts)

**Origen**: limitaciones detectadas en el smoke del hito 12 del sprint
`feature/local-agent` (ver `docs/progreso_2026-05-08-cont.md`).

**Objetivo**: cerrar el cliente local como pieza apta para producción
real, no sólo demo. Sin estos dos bloques no hay tag `v0.2.0`.

**Why**: el MVP que cerró el sprint anterior funciona como prueba de
concepto pero no cubre dos casos de uso fundamentales que el operario
medio necesita en producción:

1. Configurar el escaneo (modo color, resolución, fuente) por captura.
2. Ejecutar lógica del cliente cuando el lote sale del SaaS (crear
   carpetas custom, renombrar, unir PDFs, hablar con BD/ERP del
   cliente, llamar a APIs internas no accesibles desde el SaaS).

**How to apply**: rama nueva `feature/local-agent-d` desde el HEAD del
sprint anterior (`43db10e`). Dos pilares independientes que se pueden
paralelizar si conviene; los hitos están ordenados por dependencias.

---

## Pilar 1 — Opciones de escaneo dinámicas

### Hito 13 — `/scanners/{name}/options` + `ScannerOptionsDialog`

**Estimación**: 1 sesión.

**Backend agente**:

- `GET /scanners/{name}/options` que delega en
  `scanner_service.get_device_options(name)` (ya existe en desktop;
  retorna `list[DeviceOption]` con `name/title/type/constraint/values`).
- Cache análogo al de `/scanners` (TTL 60s + `?refresh=true`) — abrir
  el dispositivo SANE para query es caro y libsane-pixma sigue ahí.
- Schema `DeviceOptionInfo` en `saas_schemas` (réplica del DTO del
  desktop pero sin SQLAlchemy) para no importar `app.models.*` en el
  agente.

**Endpoints `/scan-*` del agente**:

- Aceptar parámetro opcional `options: dict[str, Any]` con los
  overrides que el operario eligió.
- Pasarlos a `scanner.acquire(image_config=..., overrides=options)` —
  el método `_apply_options` del `SaneScanner` ya consume un dict.
- Validar que sólo se aceptan opciones conocidas (whitelist por
  query a `get_device_options`) para no permitir setear cualquier
  cosa.

**Frontend**:

- Composable `useScannerOptions(scannerName)` que hace
  `GET /scanners/{name}/options` con cache (Pinia) y expone
  `options: Ref<DeviceOption[]>`.
- Componente `ScannerOptionsDialog.vue`:
  - Se abre al pulsar 🖨 Flatbed o 🖨 ADF (o un nuevo botón
    "🖨 Configurar y escanear").
  - Renderiza dinámicamente los controles según el tipo de opción
    (combo / number / boolean / range slider).
  - Botón "Recordar para esta aplicación" que persiste el dict
    (`PATCH /api/applications/{id}` añadiendo `scan_defaults_json`).
  - Botón "Escanear" envía las opciones al endpoint del agente.
- `ScanFromAgentMenu.vue` reescrito para abrir el dialog en lugar
  de disparar inmediatamente (con un atajo "escanear con últimos
  defaults" para no añadir un click extra al flujo rápido).

**Persistencia**:

- Migración Alembic: `applications.scan_defaults_json TEXT NOT NULL
  DEFAULT '{}'`.
- `ApplicationOut` schema añade `scan_defaults: dict`.
- El agente al recibir el escaneo no consulta el SaaS para defaults
  (el frontend ya inyecta el dict completo en el body) — mantiene la
  separación.

**Tests**:

- Agente: `GET /scanners/{name}/options` happy + 503 + cache + 401.
- Agente: `/scan-*` con `options` válido + con clave no whitelisted
  (rechazo).
- Frontend: composable + dialog renderizado dinámico + persistencia.

**Tripwires**:

- Desktop: 869, sin cambios.
- Backend web: 336 + 1-2 (migración + scan_defaults expuesto).
- Agente: 108 + 6-8 (options + override en scan).
- Frontend: 505 + 8-10 (dialog + composable).

**Smoke al final del hito**: con el Canon DR-M160, escanear ADF a
200 dpi en gris (no defaults), verificar que las páginas suben en gris
y resolución 200.

---

## Pilar 2 — Transfer scripts en el cliente

### Hito 14 — Modo `local_script` en `transfer_json` + ejecución básica

**Estimación**: 1.5 sesiones.

**Modelo y schema**:

- `transfer_json` actual soporta `{mode: "folder"|"script", ...}` en
  desktop. La web hoy sólo usa `folder`. Añadir `mode: "local_script"`
  con campos:
  - `script: str` — código Python.
  - `script_lang: "python3"` (futuro: bash/powershell).
  - `requires_pipeline: bool` — bloquea ejecución si el pipeline no
    se ha corrido.
- Migración Alembic: opcional, depende de cómo serialicen los modes
  hoy. Probablemente no toca DDL si el JSON ya admite formas nuevas.

**Agente**:

- `POST /transfer-batch-script` (nuevo endpoint, no reusar
  `/transfer-batch` para no romper hito 11):
  - Body: `{batch_id, transfer_config}` donde `transfer_config` viene
    de `app.transfer_json` con `mode: "local_script"`.
  - El agente descarga el ZIP del SaaS (mismo flujo de hito 11),
    extrae a un tmp, construye `BatchContext` + `list[PageContext]` a
    partir del manifest, ejecuta el script vía `ScriptEngine`.
  - Built-ins inyectados: `app`, `batch`, `pages`, `tmp_dir`
    (`Path` con todos los PNGs ya extraídos), `log`, `http` (httpx),
    `re`, `json`, `Path`, `datetime`. Sin acceso a la BD del SaaS.
  - Retorna `{ok, output, errors, files_written}` para que el SaaS
    registre la operación.
- Importación lazy del `ScriptEngine` desde `app/services/` — mismo
  patrón que con `scanner_service` (no arrastra SQLAlchemy al
  PyInstaller).

**Frontend**:

- En el configurador web, pestaña "Transferencia" gana radio para
  elegir modo: Folder local / ZIP / **Script local**.
- Editor CodeMirror con highlighting Python (ya hay en
  `EventsEditorView`), mismo placeholder y cheatsheet de built-ins.
- Botón "Validar sintaxis" llama al agente para compilar sin
  ejecutar.

**Tests**:

- Agente: ejecución de script con context manifest real + sandbox de
  fallos (script lanza, log de errores, no derriba el endpoint).
- Frontend: editor del modo local_script + validación.

### Hito 15 — Built-ins extra: `db` y `pdf`

**Estimación**: 1 sesión.

- **`db` built-in**: wrapper sobre `psycopg`/`pyodbc`/`sqlite3` para
  que el script se conecte a BD del cliente:
  ```python
  with db.connect("postgresql://user:pwd@host/db") as conn:
      conn.execute("INSERT INTO documentos VALUES (%s, %s)", (...))
  ```
  Sólo conexiones que el script declara — el agente no abre nada por
  su cuenta. Documentar el riesgo de credenciales en claro en el
  script (mejorar después con secrets vault del cliente).
- **`pdf` built-in**: wrapper sobre PyMuPDF (`fitz`) para
  unir/renombrar PDFs:
  ```python
  pdf.merge([page.image_path for page in pages], output_path)
  pdf.save_with_metadata(output_path, title=batch.fields["nuhsa"])
  ```

**Tests**: cada built-in con un test que simula un caso real (insert
en BD sqlite local, merge de 3 PDFs).

### Hito 16 — Editor de scripts en configurador + smoke

**Estimación**: 0.5-1 sesión.

- El editor del Hito 14 gana ejemplos rápidos (snippets) para los
  casos típicos: nombrado por barcode, merge a PDF/A, inserción en BD.
- Smoke real con el Canon DR-M160: escanear lote → ejecutar pipeline
  con un script que extrae un campo → ejecutar transfer_script que
  crea una carpeta `{año}/{barcode}/` y mueve los PNGs ahí.

### Hito 17 — Smoke completo + tag v0.2.0

**Estimación**: 0.5 sesión.

- Repetir el smoke del hito 12 con la cadena enriquecida (opciones de
  escaneo + transfer script + un pipeline real con barcode + script).
- Documentar el flujo en MkDocs (`docs-web/local-agent-flow.md`).
- Tag `v0.2.0` para SaaS si todo OK.

---

## Decisiones arquitectónicas pendientes (resolver al iniciar)

- **¿Whitelist de opciones de escaneo o abrir libre?** Dejar al
  operario configurar todo lo que SANE acepta es más potente; pero
  algunas opciones (`page-width`, `page-height` en mm) requieren
  validación cruzada. Empezar con whitelist conservadora (mode,
  resolution, source, brightness, contrast, duplex) y expandir bajo
  demanda.
- **¿Dónde almacena el script su estado intermedio?** Si el script
  corre 5 minutos y el agente cae, ¿qué? Para el MVP del Hito 14:
  ejecución síncrona, si peta el operario lo reintenta. Async
  background queda fuera de alcance.
- **¿El SaaS conoce qué scripts existen en cada agente?** No.
  `transfer_json.script` se almacena en el SaaS (`applications`) pero
  el agente lo ejecuta. Ningún agente puede inventarse otro script.
  Esto da auditabilidad: el script viaja del SaaS al agente, no al
  revés.
- **¿`db` builtin es opcional?** Sí. Si el cliente no usa BD, no
  importa. Pero las dependencias `psycopg`/`pyodbc` añadirían peso al
  PyInstaller. Considerar: hacer el `db` lazy-import (igual que
  `scanner_service`) para que el binario del agente no tenga que
  empaquetar drivers que el cliente no use.

## Tripwires que el sprint NO puede romper

- **Desktop**: 869 tests verde tras cada hito. El cliente local
  comparte código (`scanner_service`, `ScriptEngine`,
  `image_pipeline`), cualquier refactor debe ser aditivo o
  backwards-compatible.
- **Web SaaS**: 336+ tests verde. El frontend SI cambia (configurador
  + workbench) pero la lógica del backend del SaaS apenas se toca
  (sólo `applications.scan_defaults_json` y endpoint de validación
  de script).
- **Agente**: tests crecen monotónicamente. Cada hito añade tests, no
  los borra.

## Riesgos identificados

- **PyInstaller con `db` builtin**: psycopg necesita libpq dinámica;
  pyodbc necesita el driver ODBC instalado en el cliente. El binario
  del agente puede crecer mucho. Mitigación: empezar con sólo sqlite
  en el `db` builtin (cero dependencias extra) y dejar
  postgres/odbc/oracle para hito posterior.
- **Scripts maliciosos por error humano**: un operario admin puede
  poner `os.system("rm -rf /")`. El agente corre con permisos del
  usuario, no root, así que el daño está acotado pero no es cero.
  Documentar el riesgo en el editor (banner "los scripts se ejecutan
  con los permisos del usuario que arranca el agente").
- **Drift entre `app/pipeline/page_context.py` y los DTOs que el
  agente recibe**: el agente importa `PageContext` del desktop —
  tests del agente deben validar la deserialización del manifest del
  SaaS al `PageContext` que el script consume. Sin este puente las
  páginas llegarían "vacías" al script.

## Estado de partida

- Rama: `feature/local-agent-d` (a crear desde `43db10e` al iniciar).
- Tests al arrancar: 1818 passing (desktop 869 + web back 336 +
  agente 108 + frontend 505).
- Documentación de referencia: `docs/progreso_2026-05-08-cont.md`,
  `app/services/scanner_service.py` (`get_device_options`),
  `app/services/transfer_service.py` (modo `script` del desktop),
  `app/services/script_engine.py` (compilación + sandbox).
