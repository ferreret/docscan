# 📋 Changelog

Todos los cambios relevantes de DocScan Studio están documentados en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [Unreleased]

## [0.1.6] - 2026-07-28

### ✨ Salto directo a página en el visor

- El contador `N / M` de la barra flotante del visor **es editable**: clic, teclear
  el número y pulsar Intro lleva a esa página. Pensado para lotes largos, donde
  llegar a la página 427 de 600 a golpe de flecha no es viable. Escape o hacer clic
  fuera cancelan y restauran el valor. Los números fuera de rango se ignoran.
- Mientras se escribe en el contador, los atajos de tecla simple (flechas,
  Inicio/Fin y **Supr**) quedan desactivados: de lo contrario el atajo de ventana
  tiene prioridad sobre el campo de texto y `Supr` borraría una página en lugar de
  un dígito.

### ✨ Las operaciones de imagen pueden alterar el documento entregado

- Nueva casilla **«Guardar el resultado en el fichero de la página»** en el paso de
  operación de imagen. Hasta ahora las ImageOps solo afectaban a la imagen que
  circula por el pipeline —preparación para leer barcodes u OCR— y el fichero que
  se archivaba y transfería conservaba el original del escáneo. Eso es razonable
  para `FxGrayscale` o `ConvertTo1Bpp`, pero no para `AutoDeskew`,
  `CropWhiteBorders`, `Rotate` o `RemoveHolePunch`, donde el operador da por hecho
  que el documento sale enderezado y recortado. La única alternativa era escribir
  un script con `pipeline.replace_image()`.
- **Desactivada por defecto**: las aplicaciones existentes se comportan
  exactamente igual y no hay migración que aplicar.
- La casilla guarda una **instantánea de ese paso**, no el estado final del
  pipeline: se puede enderezar y archivar, y binarizar después solo para leer.
- El **worker desatendido** también persiste ahora la imagen procesada. Antes no
  lo hacía en ningún caso, así que el mismo pipeline transfería imágenes
  distintas según se ejecutara desde el workbench o sin supervisión.

### 🐛 Correcciones de robustez

- **La caché de scripts se indexa por contenido, no por identificador de paso.**
  Antes, editar un script podía seguir ejecutando la versión anterior si el motor
  sobrevivía al guardado, porque la entrada de caché se buscaba por `step.id`.
  Ahora la clave es el hash del código fuente y una edición se detecta sola; las
  versiones ya compiladas se reutilizan sin recompilar.
- **Los identificadores de paso se sanean al cargar el pipeline.** Un id vacío,
  ausente o duplicado rompía de forma difusa todo lo que indexa por id (caché de
  scripts, `skip_step`, `skip_to`, el límite de `repeat_step`). Ahora se regeneran
  al deserializar, dejando aviso en el log, en lugar de fallar más tarde y lejos de
  la causa.
- **Escritura atómica** (temporal + `rename`) del almacén cifrado de credenciales,
  de su clave y de los ficheros de exportación de aplicaciones. Un cierre a
  destiempo ya no puede dejar un `secrets.enc` truncado —y por tanto ilegible por
  completo— ni un pack de aplicación a medias.
- **Los ficheros de un lote se borran solo después de que la base de datos confirme
  la eliminación.** Al eliminar lotes o páginas, el borrado en disco se difiere al
  `commit`; si la transacción se revierte, las imágenes siguen en su sitio. El
  orden anterior (borrar primero, confirmar después) destruía imágenes de forma
  irrecuperable si la base de datos rechazaba el borrado.
- **Un script colgado ya no deja sin scripting al resto del lote.** El motor
  ejecuta los scripts en un hilo con límite de tiempo, pero ese hilo no se puede
  matar: al expirar el plazo se quedaba ocupado para siempre y todas las páginas
  siguientes se encolaban detrás, agotando el timeout una a una. En un lote de 600
  páginas eran horas de esperas con el scripting muerto y sin aviso. Ahora, tras un
  timeout, el motor descarta ese hilo y sigue con uno limpio.
- **Las expresiones regulares de usuario se evalúan con límite de tiempo** (1 s,
  criterio *fail-open*), tanto en el filtro del paso de barcode como en la
  validación del barcode manual —esta última corría en el hilo de la interfaz, así
  que un patrón con *backtracking* catastrófico congelaba la ventana entera. Se
  añade la dependencia `regex`: el `re` de la biblioteca estándar no admite timeout
  y no libera el GIL mientras evalúa, de modo que ningún vigilante escrito en
  Python puede rescatarlo.
- **Cancelar deja de reportarse como terminación correcta.** `ScanWorker` anunciaba
  el total completo de páginas tras una interrupción, y `RecognitionWorker` emitía
  la misma señal de «todo procesado» que en el camino normal —la señal que marca el
  lote como leído y dispara la auto-transferencia—. Ambos emiten ahora una señal
  propia de cancelación con el recuento real. Hoy la interrupción solo ocurre al
  cerrar la ventana, así que no había daño observable; quedaba como una mina para
  el día que se añada un botón de cancelar.

## [0.1.5] - 2026-07-22

### 🐛 La app desktop aplica migraciones al arrancar

- **Corregido el crash de arranque contra una base de datos preexistente**
  (`no such column: applications.notifications_json`). La app inicializaba el
  esquema con `create_all()`, que crea tablas nuevas pero **nunca añade columnas**
  a tablas ya existentes ni aplica migraciones. Al evolucionar el modelo (p.ej. el
  webhook de v0.1.4 añadió `notifications_json`), cualquier instalación con una BD
  anterior quedaba inservible.
- Ahora el arranque aplica migraciones Alembic de forma robusta a tres estados de
  BD: **nueva** (crea el esquema desde las migraciones), **versionada** (aplica lo
  que falte) y **heredada** (creada con `create_all` sin control de versión: se
  reconcilian por reflexión las columnas ausentes del modelo y se adopta en
  Alembic). Los datos existentes se preservan.
- Migraciones internas hechas idempotentes para no romper el proceso en SQLite.
- **Nota**: quien tenga la v0.1.4 instalada y sufriera el crash queda arreglado al
  actualizar; no hay que hacer nada manualmente.

## [0.1.4] - 2026-07-22

### ⬆️ Actualización de dependencias mayores

- **opencv-python 4.13 → 5.0.0.93** (salto de versión mayor). El uso del proyecto
  es 100 % API core (`cvtColor`, `resize`, `threshold`, morfología, `warpAffine`,
  `HoughCircles`…), no afectada por los breaking de OpenCV 5 (retirada del C API
  legacy, G-API/ML movidos a `contrib`, cambios de DNN/ONNX).
- **anthropic 0.84.0 → 0.117.1**. La superficie usada (`Anthropic()`,
  `messages.create`, iteración de bloques de contenido) es estable.
- **PySide6 6.10.2 → 6.11.1**, **SQLAlchemy 2.0.48 → 2.0.51**,
  **zxing-cpp 3.0.0 → 3.1.0**, **PyMuPDF 1.27.1 → 1.28.0**,
  **openai 2.26.0 → 2.46.0**.
- Sin cambios de código: los 879 tests siguen en verde y el smoke de importación
  de servicios y clientes IA pasa. Todos los paquetes tienen _wheels_ para
  Python 3.14.

### ✨ Notificaciones webhook por aplicación

- **Webhook configurable por aplicación**: nueva pestaña «Notificaciones» en el
  configurador para definir un webhook (URL, método POST/GET, cabeceras HTTP y
  timeout) que se dispara al completar o fallar la transferencia de un lote.
  Hasta ahora el servicio de notificaciones existía pero el webhook llegaba
  siempre `None` (un `TODO` en el worker); ahora se carga de la configuración.
- Persistencia en la columna nueva `applications.notifications_json` (migración
  Alembic `c1d5e9f34b28`); la estructura JSON anidada reserva sitio para email
  SMTP en el futuro. La config viaja al exportar/importar aplicaciones.
- Email SMTP queda pendiente (requiere cifrado Fernet del password).

### 🔧 Infraestructura de tests y unificación de Python

- **Unificación en Python 3.14**: desarrollo, CI e instaladores pasan a usar
  todos Python 3.14 (antes se desarrollaba en 3.14 pero se construía en 3.13).
  Esa divergencia había causado el bug de portabilidad de `except A, B:`
  (PEP 758). Con toda la cadena en 3.14, `ruff.toml` vuelve a `target-version =
  py314` y `ruff format` normaliza los `except` a la sintaxis 3.14. CI y
  `release.yml` construyen con 3.14.
- **Suite no interactiva y sin hardware**: nuevo `tests/conftest.py` global que
  (1) mockea todos los modales de Qt para que ningún test espere un clic,
  (2) inyecta un módulo `sane` falso antes de recolectar tests —ninguna ruta
  abre el escáner USB real, se elimina el prompt de administrador (polkit) y los
  ~33 s de enumeración de hardware—, y (3) autodescarta los tests de la web
  archivada cuando faltan sus dependencias. `pytest tests/` sin flags:
  861 passing en ~24 s, cero interacción. El CI delega en el conftest en vez de
  enumerar `--ignore`.

## [0.1.3] — 2026-07-21

### 🧹 Mantenimiento y saneamiento del desktop

La versión web SaaS quedó **archivada**; el proyecto se enfoca en DocScan
Desktop. Auditoría completa en `docs/auditoria_desktop_2026-07-21.md`.

- **Fix**: `--direct-mode` estaba roto por un import inexistente (`get_scanner`
  → `create_scanner` en `main.py`). Añadidos tests de regresión del modo directo.
- **Seguridad**: actualizadas dependencias con CVEs conocidos — Pillow
  12.1.1→12.3.0, cryptography 46.0.5→48.0.1, pydantic-settings→2.14.2,
  pytest→9.0.3. `pip-audit` limpio.
- **Limpieza**: eliminado `app/providers/` (código muerto desde el borrado de
  AiStep). Barrido `ruff check --fix` + `ruff format` sobre todo el código
  desktop; añadido `ruff.toml` (primera config de lint del proyecto).
  `ruff check .` totalmente limpio.
- **Tests**: mockeado el modal `QMessageBox.warning` que colgaba la suite; y
  mockeada la capa SANE en `test_scanner_service.py` (antes hacía enumeración
  real de hardware, ~33s y capaz de colgarse). Suite completa 861/861 en ~22s.
- **CI**: nuevo workflow `.github/workflows/ci.yml` (lint + tests en push/PR) y
  `pytest.ini` con `--timeout` por defecto contra cuelgues.
- **Portabilidad Python 3.13**: 20 bloques usaban `except A, B:` sin paréntesis,
  sintaxis exclusiva de Python 3.14 (PEP 758) que rompía la importación en 3.13
  (CI e instaladores). Corregido a `except (A, B):`; `ruff.toml` fijado a
  `target-version = py313` para que `ruff format` no vuelva a quitar los
  paréntesis. Detectado por el nuevo CI.

---

### 🗄️ Histórico versión web SaaS (archivada 2026-07-21)

> Las secciones siguientes documentan la versión web SaaS, archivada. Se
> conservan como referencia; no forman parte de las releases del desktop.

#### 🛡️ Sprint Superadmin (versión web SaaS) — 2026-05-05

Plataforma multi-tenant lista para SaaS con jerarquía de roles `superadmin > company_admin > operator`. Sólo el equipo de TecnoMedia (rol `superadmin`) puede crear tenants y administradores; el registro público está deshabilitado.

#### ✨ Backend (`web/api/`)

- **CLI bootstrap idempotente** del primer superadmin:
  ```
  docker compose exec api python -m web.api.bootstrap superadmin \
      --email admin@tecnomedia.es --password ********** \
      --display "Admin TecnoMedia"
  ```
  Crea (o reutiliza) el tenant especial `TecnoMedia` y un usuario con rol `superadmin`. Volver a ejecutarlo con el mismo email es no-op.
- **Registro público eliminado**: `POST /api/auth/register` devuelve 404. La aceptación de invitaciones (`/accept-invitation/:token`) sigue siendo el camino para usuarios añadidos por invitación.
- **Login bloqueado en tenants suspendidos**: `tenant.active=False` rechaza el login con 401 y el `/auth/me` también, aunque el JWT siga vigente.
- **Modelo `AuditLog`** + helper `web/api/audit.py::audit(...)`: registra cada mutación administrativa (`tenant.created/updated/deleted`, `user.created/updated/deleted`) con actor, target y payload JSON.
- **Endpoints `/api/admin/tenants`** (5) — superadmin sólo:
  - `GET /admin/tenants` (paginado, con stats por tenant)
  - `POST /admin/tenants` (crea tenant + primer company_admin)
  - `GET /admin/tenants/{id}` (detalle + lista de usuarios)
  - `PATCH /admin/tenants/{id}` (name | plan | active)
  - `DELETE /admin/tenants/{id}` (hard-cascade BD + storage; rechaza con 409 si hay batches `running`/`transferring` o si el tenant es TecnoMedia)
- **Endpoints `/api/admin/users`** (4) — superadmin sólo, cross-tenant:
  - `GET /admin/users` (filtra por `?tenant_id=`)
  - `POST /admin/users` (crea directamente en cualquier tenant)
  - `PATCH /admin/users/{id}` (role | active | display_name)
  - `DELETE /admin/users/{id}`
  - Guards: rechaza con 409 al degradar/desactivar/borrar al último superadmin global o al último company_admin activo del tenant. Self-modify desde aquí también devuelve 409 (defense-in-depth).

#### ✨ Frontend (`web/frontend/`)

- **Store Pinia `admin.ts`** + tipos TypeScript que reflejan los schemas (`Tenant`, `TenantStats`, `TenantDetail`, `AdminUserListItem`, etc.).
- **Rutas `/admin/tenants`, `/admin/tenants/new`, `/admin/tenants/:id`** con `meta.superadmin: true`.
- **Guard global `enforceRoleAccess`** en el router:
  - `superadmin` en una ruta no `/admin/*` → redirige a `/admin/tenants`.
  - cualquier rol distinto de `superadmin` accediendo a `/admin/*` → redirige a `/`.
- **AppLayout dual**: sidebar reducido a "Tenants" + header "TecnoMedia · Administración" cuando el rol es `superadmin`. Sidebar normal para `company_admin`/`operator`.
- **Vista de listado**: tabla con stats por tenant, badge coloreado por plan, toggle Activo/Suspendido inline, eliminar con confirmación del nombre exacto.
- **Vista de creación**: formulario tenant + primer admin con validación local de password (≥8 caracteres) y feedback de errores 409 (email duplicado, plan inválido).
- **Vista de detalle**: edita name/plan/active del tenant + CRUD completo de sus usuarios (cambio de rol, toggle activo, delete con confirm, modal "Crear usuario").

#### 🧪 Tests añadidos en el sprint

- Backend: 81 tests TDD cubren bootstrap, audit, admin_tenants, admin_users, registro retirado y tenant suspendido. Suite web: **298 passing**.
- Frontend: 49 tests TDD nuevos para store, guard de rol, AppLayout y las 3 vistas admin. Suite frontend: **460 passing**.

#### 🔍 Smoke e2e

- `scripts/smoke_superadmin.sh` — matriz curl de 21 casos contra `docker compose` (registro 404, login + me, /admin/* con 3 roles, CRUD tenants, CRUD users cross-tenant, guards 409 último-admin / self-modify, suspensión + login bloqueado, cascade delete, protección de TecnoMedia).
- Smoke visual con Playwright recogido en `docs/screenshots/smoke-superadmin/`: listado, formulario de creación, detalle del tenant y bloqueo del guard cuando un company_admin intenta entrar a `/admin/*`.

#### 📝 Notas de migración

- **Nueva tabla `audit_logs`**: aplicar `alembic upgrade head` (la migración `a3b8d4e2f7c9_add_audit_logs.py` se ejecuta automáticamente en el `docker-bootstrap-db.py`).
- **Sin cambios** en la app de escritorio. Esta release sólo afecta a la versión web SaaS.

---

## [0.1.2] — 2026-04-30

### 🐛 Corregido

- **Editor de Eventos del configurador**: el placeholder del editor de código estaba hardcoded a la firma de `on_app_start` y nunca cambiaba al seleccionar otro evento del combo. Ahora se actualiza dinámicamente con la firma correcta del evento elegido (`on_page_changed(app, batch, page)`, `on_key_event(app, batch, key)`, etc.) usando el catálogo `EVENT_SIGNATURES`.
- **`page.id` accesible desde `on_page_changed` en el escritorio**: el dispatcher pasaba sólo `page_index` (un entero) y un script con la firma documentada `def on_page_changed(app, batch, page)` fallaba con `missing 1 required positional argument: 'page'`. Ahora el workbench construye un `PageContext` con `id`, `page_index`, `barcodes`, `ocr_text`, `fields` y `flags`, igualando el contrato con la versión web. Los scripts antiguos con `(app, batch)` o `(app, batch, page_index)` siguen funcionando — el `ScriptEngine` filtra los kwargs por la firma de la función.

### 📝 Notas

- Sin cambios en BD ni en el formato de pipeline. Actualización in-place desde 0.1.1.

---

## [0.1.1] — 2026-04-30

### ✨ Eventos lifecycle ampliados
- **`on_batch_loaded`** y **`on_page_changed`** promocionados al catálogo del configurador (pestaña Eventos) con descripciones traducibles. Hasta ahora estos dos hooks sólo existían en la versión web; ahora también pueden definirse como scripts lifecycle convencionales en la app de escritorio, manteniendo el hook del VerificationPanel para retrocompatibilidad.
- **`page.id`** ahora accesible desde scripts lifecycle (`on_navigate_*`, `on_page_changed`, etc.). Antes el contexto sólo exponía `page_index` y `page.id` lanzaba `AttributeError`.

### 🐛 Corregido
- Warning de Qt al cerrar el launcher: `QPropertyAnimation` sobre `fixedWidth` provocaba un mensaje en consola sin efecto funcional. Limpiado.

### 📝 Notas
- Sin cambios en BD ni en el formato de pipeline. Actualización in-place desde 0.1.0.

---

## [0.1.0] — 2026-03-26

### 🚀 Distribución e instaladores
- **UI de actualización**: diálogo de descarga con barra de progreso, notas de release y verificación SHA-256
- **Banner de actualización**: notificación no invasiva en el Launcher con botones "Ver novedades", "Actualizar" e "Ignorar"
- **Botón "Buscar actualizaciones"** en el diálogo Acerca de
- **Auto-check al inicio**: comprobación de nuevas versiones en segundo plano tras arrancar
- **PyInstaller specs**: configuración de empaquetado para Linux y Windows
- **AppImage**: recipe AppImageBuilder + fichero .desktop para distribución Linux
- **Inno Setup**: script de instalador Windows con español/inglés/catalán y modo silencioso
- **CI/CD**: GitHub Actions workflow para build automático y release al crear tags `v*`
- **Informe de licenciamiento**: análisis de licencias, modelos de negocio, plataformas de venta y protección de código

### 🏗️ Infraestructura
- Rama `production` para releases estables
- Versión centralizada en `app/_version.py`
- Auto-update service con GitHub Releases API + SHA-256
- Estilos QSS para banner de actualización (tema claro y oscuro)
- 21 tests nuevos para UI de actualización (849 total)

---

## [0.1 RC] — 2026-03-26

### 📖 Documentación
- README.md completo con badges, screenshots, arquitectura, pipeline, scripting, AI Mode y roadmap
- Manual de usuario Word (.docx) con 12 capítulos y 18 figuras reales
- Documentación web MkDocs Material con 13 páginas, publicada en GitHub Pages
- 73 tooltips añadidos a 14 ficheros UI (batch manager, configurador, workbench)
- Diálogo "Acerca de" con versión, logo, stack tecnológico y copyright
- Generador de documentos clínicos de ejemplo para demos
- Auditoría de seguridad: sin API keys ni credenciales expuestas
- `.gitignore` reforzado con exclusiones de seguridad

---

## [Release 3] — 2026-03-25

### ✨ Funcionalidades
- **AI MODE**: asistente conversacional integrado en el Launcher para crear y configurar aplicaciones mediante lenguaje natural (Anthropic / OpenAI)
- **Pipeline Assistant**: asistente IA contextual por aplicación en el configurador
- **Test Pipeline** (IMG-14): ejecución del pipeline sobre imagen de muestra con resultados paso a paso
- **Export/Import** (CFG-02/03): exportar e importar aplicaciones como ficheros `.docscan` (JSON)
- **Sidebar colapsable**: panel lateral con 10 iconos vectoriales QPainter, animación de 150ms
- **Política de colisión** (TRS-05): sufijo numérico, sobreescribir o fusionar multi-página PDF/TIFF
- **Detección de páginas en blanco** (APP-05): análisis por histograma con auto-exclusión configurable
- **Splash screen**: pantalla de carga con logo, versión y progreso de inicialización

### 🚫 Descartados
- ConditionStep / HttpRequestStep — redundantes con ScriptStep + AI MODE
- Perfiles de usuario (LCH-07/BAT-05) — innecesario para mono-estación
- batch.lock (BAT-03) — foco mono-estación
- Pipeline templates (IMG-13) — cubierto por AI MODE + Export/Import

---

## [Release 2b] — 2026-03-22

### ✨ Funcionalidades
- **Panel de verificación personalizado**: widget QWidget definido por script en `verification_panel`, insertado como pestaña en el Workbench

---

## [Release 2] — 2026-03-21

### ✨ Funcionalidades
- **Internacionalización** (i18n): soporte multilenguaje para Español, English y Català con `QT_TRANSLATE_NOOP` y funciones lazy
- **Atajos de teclado**: 17 shortcuts para el Workbench (navegación, zoom, rotación, marcado, eliminación)
- **OCR estructurado**: resultados con regiones word-level y coordenadas
- **Field overlays**: visualización de regiones OCR sobre el visor de documentos
- **Compatibilidad Windows**: soporte TWAIN + WIA para escáneres, ajustes cross-platform
- **Icono de aplicación**: en títulos de ventana y barra de tareas Windows

---

## [Release 1B] — 2026-03-20

### ✨ Funcionalidades
- **ImageLib**: librería de operaciones de imagen (load, save, merge, split, DPI, color)
- **ImageConfig**: dataclass de configuración de imagen con parse/serialize
- **Pestaña Imagen**: nueva pestaña en el configurador (formato, color, compresión)
- **Mejoras de transferencia**: conversión de formato, DPI y color al exportar

### 🔧 Cambios técnicos
- Eliminación de AiStep del pipeline (absorbido por ScriptStep)
- Unificación `ai_fields` → `custom_fields` → `page.fields`
- Fix memory leak: `WA_DeleteOnClose` + `deleteLater` en ventanas secundarias
- Guard para señales tardías post-cierre de ventana
- Resume automático de pipeline al reabrir lote
- 4 migraciones Alembic aplicadas
- `requirements-dev.txt` con dependencias de desarrollo separadas

### 🐛 Correcciones
- Navegación next-barcode / next-review
- Parsing de `events_json` para string y dict
- Tamaños de ventana ampliados (configurador 950×700, workbench 1440×900)

---

## [Release 1] — 2026-03-19

### ✨ Funcionalidades

#### Infraestructura (pasos 1-5)
- Pipeline engine: steps.py, context.py, executor.py, serializer.py
- PipelineContext con control de flujo: skip_step, skip_to, abort, repeat_step
- Settings con pydantic-settings + Secrets con Fernet
- Base de datos SQLite con WAL mode obligatorio + repositorios

#### Servicios (pasos 6-11)
- **ScriptEngine**: compilación de scripts al cargar app, ejecución con timeout
- **BarcodeService**: Motor 1 (pyzbar, 12 simbologías) + Motor 2 (zxing-cpp, 14 simbologías)
- **ImagePipeline**: 23+ operaciones de imagen (deskew, crop, filtros, morfología...)
- **OcrService**: RapidOCR (primary), EasyOCR (alternative), Tesseract (fallback)
- **Proveedores IA**: Anthropic (Claude) + OpenAI (GPT-4o) con Strategy pattern
- **PipelineExecutor**: ejecución stateless con max repeat limit

#### Soporte (pasos 12-15)
- **ScannerService**: SANE (Linux) con subprocess para thread-safety
- **ImportService**: TIFF multi-página, JPEG, PNG, BMP, PDF (rasterizado con PyMuPDF)
- **BatchService**: gestión de lotes con estados y auditoría
- **TransferService**: transferencia simple a carpeta + avanzada por script
- **NotificationService**: email + webhook

#### Launcher (paso 16)
- Ventana principal con lista de aplicaciones
- Crear, editar, duplicar, eliminar aplicaciones
- Búsqueda de aplicaciones

#### Configurador (pasos 17-18)
- 6 pestañas: General, Imagen, Campos de Lote, Pipeline, Eventos, Transferencia
- Editor visual de pipeline con drag & drop
- Diálogos de edición por tipo de paso (ImageOp, Barcode, OCR, Script)
- Editor de eventos del ciclo de vida con integración VS Code

#### Workbench (paso 19)
- Panel de miniaturas con estados de color
- Visor de documentos con zoom, pan y overlays
- Panel de barcodes con tabla y contadores
- Panel de metadatos con campos dinámicos
- Panel de log en tiempo real
- Workers QThread: scan, recognition, transfer
- Drag & drop para importación

#### Batch Manager (paso 20)
- Histórico de lotes con filtros (aplicación, estación, fecha)
- Panel de detalle con estadísticas, páginas e historial
- Reabrir lotes anteriores en el Workbench
- Auto-refresco cada 20 segundos

#### Worker (paso 21)
- DocScanWorker CLI para procesamiento desatendido
- Folder watcher con watchdog

#### Tests (paso 22)
- Suite de tests con pytest + pytest-qt
- Tests de repositorios, servicios, pipeline, UI y integración

---

## Métricas del proyecto

| Métrica | Valor |
|---------|-------|
| Líneas de código (app) | 19.776 |
| Líneas de test | 11.618 |
| Ficheros fuente | 94 |
| Tests | 813 passing ✅ |
| Operaciones de imagen | 23 |
| Simbologías barcode | 14 |
| Motores OCR | 3 |
| Idiomas de interfaz | 3 |
