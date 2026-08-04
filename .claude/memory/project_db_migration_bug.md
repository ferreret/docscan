---
name: project_db_migration_bug
description: Bug de arranque contra BD preexistente (create_all no migra) destapado en campo; BD del usuario reparada; fix de fondo pendiente para v0.1.5
metadata: 
  node_type: memory
  type: project
  originSessionId: c789763b-7339-40f6-8308-87bbce5e647b
  modified: 2026-07-22T11:31:39.897Z
---

# Bug: la app desktop no migra la BD al arrancar (destapado 2026-07-22)

**Síntoma**: `python3.14 main.py` crashea contra una BD **preexistente** con
`sqlite3.OperationalError: no such column: applications.notifications_json`
(en `_run_init_global` → `ApplicationRepository.get_all()`, main.py:215/321).

**Causa raíz** (preexistente, NO de los upgrades de deps): la app arranca con
`create_tables()` = `Base.metadata.create_all()` (main.py:252), que **solo crea
tablas nuevas, nunca añade columnas** a tablas existentes. La app **no corre
`alembic upgrade` al arrancar**. Así, cuando el webhook añadió `notifications_json`
al modelo `Application`, ninguna BD ya creada recibió la columna. Los 879 tests y
el smoke GUI offscreen NO lo detectan porque crean la BD desde cero con
`create_all` (esquema completo). **Solo aparece en campo, contra BD real.** →
valida el feedback [[feedback_inline_tests_can_hide_bugs]] del usuario.

**Complicación de la cadena alembic**: `alembic upgrade head` NO es viable sobre
una BD desktop. Head único `c1d5e9f34b28`, pero entre la revisión típica desktop
`bf8a2c4d1e9a` (add tenants and users) y el head hay **3 migraciones de la web
SaaS archivada**: `e5b7c3d94f10` (unique name per tenant), `f7c9d2b85a43`
(invitations), `a3b8d4e2f7c9` (audit_logs). `e5b7c3d94f10` peta con
`ValueError: No such constraint: 'applications_name_key'` (constraint que la BD
desktop no tiene). La migración del webhook (desktop) se colgó DESPUÉS de las web
en una cadena lineal mixta.

**Reparación aplicada a la BD real del usuario 2026-07-22** (autorizada; el
classifier bloqueó la 1ª vez por ser escritura sobre producción):
- Backup: `~/.local/share/docscan/docscan.db.bak-20260722-123707` (+WAL/SHM).
- Vía quirúrgica (NO upgrade head): `ALTER TABLE applications ADD COLUMN
  notifications_json TEXT NOT NULL DEFAULT '{}'` + `alembic stamp head`
  (apuntando alembic a la BD con env var `DOCSCAN_WEB_DATABASE__URL=sqlite:///<path>`
  — env.py la usa como override de URL aunque diga "WEB").
- Verificado en copia antes de tocar la real: `repo.get_all()` → 11 apps,
  LauncherWindow arranca y renderiza las 11 apps reales. Tras aplicar a la real,
  `main.py` arranca estable en :0.0 sin crash. Revisión `bf8a2c4d1e9a`→`c1d5e9f34b28`.
- Las 11 apps reales del usuario preservadas (Códigos de Barra Exportador,
  Peticiones clínica, Prueba 22, Test Escaner, Test IA, Test OCR…).

**FIX IMPLEMENTADO 2026-07-22** (rama `fix/desktop-db-migrations`, commit `bcd17a7`,
sin mergear aún): `main.py` llama `run_migrations(engine)` (en `app/db/database.py`)
en vez de `create_tables`. Robusto a 3 estados: vacía→`upgrade head`;
versionada→`upgrade head`; legacy `create_all` sin `alembic_version`→
`_reconcile_missing_columns` (ALTER ADD por reflexión del modelo) + `stamp head`.
Soporte: `e5b7`/`f7c9`/`a3b8` idempotentes (guards `inspect`) para que `upgrade
head` no pete en SQLite desktop; `env.py` reusa la conexión vía
`cfg.attributes["connection"]` + `configure_logger=False`; hiddenimports de
alembic en los `.spec`. **NO se separaron las cadenas web/desktop** (habría roto
la web, que depende de la cadena completa); en su lugar se hicieron idempotentes
las 3 migraciones web que petaban. **Validado**: 883 tests (4 nuevos en
`test_migrations.py`), ruff limpio, arranque real (offscreen, `DOCSCAN_DATABASE__PATH`)
contra BD legacy (reconcilia notifications_json) y nueva (crea desde cero) sin crash.
**Riesgo residual único**: empaquetado alembic en PyInstaller (`datas` ya lo incluía;
hiddenimports añadidos) — solo se confirma en un build real.
**Pendiente**: merge a main, docs (CHANGELOG/version→0.1.5), tag v0.1.5 y vigilar build.
La **v0.1.4 quedó publicada con el bug** (dejar como release con bug conocido).
La BD del usuario ya reparada está en head → compatible con el nuevo código (no
requiere recrearse; opción de higiene, no necesaria).

**Dato del usuario (2026-07-22)**: las 11 apps de SU BD local son de prueba y
**se pueden borrar sin problema** — su BD de desarrollo se puede recrear limpia
desde alembic (opción de higiene tras implementar el fix). OJO: esto aplica solo
a su entorno; el fix de v0.1.5 para usuarios finales DEBE preservar datos reales
(lotes/páginas escaneados), y la Opción A con alembic ya lo hace.

**Enfoque del fix DECIDIDO (Opción A, criterio de largo plazo del usuario)**:
alembic como fuente de verdad también en desktop. La app corre migraciones al
arrancar vía `run_migrations(engine)` en database.py (3 caminos: vacía→upgrade;
versionada→upgrade; legacy sin alembic_version→reconciliar columnas por reflexión
+ stamp head). Requiere: `e5b7c3d94f10` idempotente (guards inspect), empaquetar
alembic en PyInstaller, mitigar fileConfig/logging de env.py, tests. Plan en
`~/.claude/plans/tender-crafting-lemur.md`.

Ver [[feedback_no_romper_desktop]].
