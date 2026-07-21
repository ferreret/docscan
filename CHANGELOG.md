# 📋 Changelog

Todos los cambios relevantes de DocScan Studio están documentados en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [Unreleased]

### 🧹 Mantenimiento desktop — 2026-07-21

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
- **Tests**: mockeado el modal `QMessageBox.warning` en `test_create_duplicate_app`
  que colgaba la suite de forma intermitente.

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
