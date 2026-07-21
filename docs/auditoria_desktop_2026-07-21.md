# Auditoría del proyecto DocScan Desktop — 2026-07-21

**Contexto**: el 2026-07-21 se decide archivar la versión web SaaS y focalizar el
proyecto exclusivamente en DocScan Desktop. Esta auditoría establece el estado
de partida. Rama auditada: `main` (HEAD `19cfebf`). Versión del código: **0.1.2**.

---

## Resumen ejecutivo

El desktop está **sano en su núcleo**: el pipeline, el motor de scripts, la capa
de threading Qt y la gestión de sesiones/BD cumplen las reglas críticas del
proyecto sin excepciones. La suite de tests desktop pasa al completo
(**858/858**) con una cobertura global del **65%**.

Se han encontrado **1 bug funcional real** (modo `--direct-mode` roto por un
import inexistente), **código muerto** heredado de refactors antiguos,
**dependencias con vulnerabilidades conocidas** (Pillow), y una cantidad
moderada de deuda de estilo y documentación desactualizada. Nada compromete
integridad de datos, credenciales ni responsividad de la UI.

---

## 1. Hallazgos críticos

### 1.1 Bug: `--direct-mode` roto (ImportError)

`main.py:119` importa `get_scanner` de `app/services/scanner_service.py`, pero
esa función no existe — la API pública es `create_scanner(backend)`
(`scanner_service.py:779`). Cualquier ejecución
`python3.14 main.py --direct-mode "App"` lanza `ImportError`. No hay test que
cubra ese camino, por eso pasó inadvertido. **Fix trivial** (renombrar el
import y la llamada).

### 1.2 Vulnerabilidades en dependencias (pip-audit)

| Paquete | Versión | Avisos | Fix |
|---|---|---|---|
| **pillow** | 12.1.1 | 5 CVEs + 8 PYSEC (proceso de imágenes — superficie directa de DocScan) | **12.3.0** |
| pydantic-settings | 2.13.1 | GHSA-4xgf-cpjx-pc3j | 2.14.2 |
| pytest | 9.0.2 | PYSEC-2026-1845 (solo dev) | 9.0.3 |

Pillow es prioritario: DocScan carga imágenes y PDFs de origen externo.

---

## 2. Calidad del código (`app/`, `main.py`, `docscan_worker/`)

### Cumplimiento de reglas críticas del CLAUDE.md — ✅ correcto

- WAL mode activado en el único punto de creación de engine (`app/db/database.py:32-38`), reutilizado por worker y main.
- Sessions siempre en context manager; repositorios reciben Session por parámetro.
- API keys cifradas con Fernet (`config/secrets.py`, clave 0600); ninguna en texto plano ni en ORM.
- Scripts compilados una vez por `step.id`; errores de ScriptStep van a `page.flags.script_errors` sin parar el pipeline; `repeat_step` limita con `PipelineAbortError`.
- BarcodeStep agnóstico de roles. Sin `print()`, sin rutas hardcoded, type hints completos en API pública.
- Workers todos en QThread con Signal; ventanas no-principales con `WA_DeleteOnClose` + `deleteLater()`. Sin bloqueos del hilo UI detectados.
- Capas desacopladas (ningún import de `app.ui` desde services/pipeline).

### Deudas encontradas

- **Código muerto — `app/providers/`** (~400 LOC): `AnthropicProvider`/`OpenAIProvider`/`BaseProvider` no se usan desde ningún flujo (restos del `AiStep` eliminado el 2026-03-20). Los asistentes IA vigentes (`ai_mode_assistant.py`, `pipeline_assistant.py`) crean su propio cliente y duplican la lógica de retry. Decidir: eliminar el paquete o migrar los asistentes a usarlo.
- **28 `setStyleSheet()` inline en 13 ficheros** (about_dialog, update_dialog, test_pipeline_dialog, sidebar…) — contra la regla "estilos en .qss". Mayoría son estilos condicionales por estado; resolubles con propiedades dinámicas + selectores QSS.
- **Nomenclatura confusa**: `app/pipeline/test_executor.py` y `app/workers/test_pipeline_worker.py` son código de producción (feature "Probar pipeline") con prefijo `test_`. Sin `testpaths` configurado, un `pytest` sin argumentos los intenta recolectar. Renombrar (p.ej. `instrumented_executor.py`) o añadir `testpaths = tests` a la config.
- **TODO real único**: `docscan_worker/worker_main.py:465` (y patrón repetido en :479) — `webhook=None, # TODO: cargar de app config`.
- **Lint**: ruff reporta 58 avisos (42 unused-import, 11 lambda-assignment, 40 auto-arreglables) y 68/100 ficheros sin `ruff format`. Barrido global pendiente desde hace meses.

---

## 3. Tests y cobertura

- **858/858 passing** (excluyendo los tests web/arq, que requieren dependencias no instaladas tras el archivo de la web: `tests/test_web_*.py`, `tests/test_arq_*.py`, `tests/test_pipeline_runner_events.py`).
- **Cobertura global: 65%** (10.858 líneas). Zonas débiles:

| Módulo | Cobertura |
|---|---|
| `app/ui/workbench/workbench_window.py` (1.241 stmts) | 37% |
| `app/ui/launcher/ai_mode_panel.py` | 32% |
| `app/ui/launcher/app_change_preview.py` | 18% |
| `app/ui/workbench/scanner_config_dialog.py` | 12% |
| `app/workers/pipeline_assistant_worker.py` | 0% |
| `app/ui/splash_screen.py` | 0% |

- **Hueco de CI**: no existe workflow de tests/lint en push/PR — solo build en tag (`release.yml`) y docs (`docs.yml`). Ninguno depende de la web.

### Fragilidad de la suite descubierta durante el barrido (pre-existente)

Dos tests dependen del entorno gráfico/hardware y pueden colgar la suite completa; ambos pasaban en el run inicial de la sesión y empezaron a colgar después, según el estado del gestor de ventanas y del escáner:

1. **`test_launcher.py::test_create_duplicate_app`** invocaba `LauncherWindow._create_app` con un nombre duplicado, que abre un `QMessageBox.warning` **modal sin mockear** (`launcher_window.py:339`). En un display real bloquea el hilo indefinidamente esperando un clic. **Corregido** en esta sesión mockeando `QMessageBox.warning` en el test. Recomendable auditar el resto de la UI en busca de modales sin mock en tests (`QMessageBox.information` en `launcher_window.py:279`, diálogos `.exec()`), idealmente con un fixture `conftest.py` autouse que neutralice modales.
2. **`test_scanner_service.py`** ejecuta **enumeración real de SANE** (`sane.init()`, descubrimiento de dispositivos). Es lento (~33s aislado) y puede colgar >60s según el estado del escáner/red. Un test unitario no debería tocar hardware real. Follow-up: mockear la capa SANE (`_sane`/`python-sane`) para que sea determinista y rápido. Mientras tanto, para iterar rápido se puede excluir con `--ignore=tests/test_scanner_service.py`.

Recomendación transversal: añadir `pytest-timeout` a `requirements-dev.txt` y un `--timeout` por defecto en la config de pytest, para que un cuelgue se convierta en fallo con nombre en vez de bloquear toda la suite.

---

## 4. Base de datos y migraciones

10 migraciones Alembic, cadena lineal, head única — pero la **head
(`a3b8d4e2f7c9`, add_audit_logs) y las 4 anteriores son de la web SaaS**
(tenants, users, tenant_id, invitations, audit_logs). Un desktop que haga
`alembic upgrade head` crea tablas multi-tenant que no usa. Las migraciones
puramente desktop terminan en `4a90ab536830`. Opciones: documentarlo como
inofensivo, o crear una base desktop propia si molesta.

---

## 5. Documentación

| Documento | Estado |
|---|---|
| `README.md` | Insignia de versión dice `0.1_RC` (código: 0.1.2); "813 tests"; sección web SaaS activa |
| `CHANGELOG.md` | Releases al día, pero `[Unreleased]` está lleno del sprint web superadmin — separar antes de v0.1.3 |
| `docs/INFORME_PROYECTO.md` | Fechado 2026-03-10: "67 módulos / 9.086 LOC / 91%". Realidad: ~104 ficheros / ~22.600 LOC |
| MkDocs (`docs-web/`) | Versiones correctas; el nav publica sección "Versión Web" de la parte archivada |
| `docs/` | 38 ficheros `progreso_*.md` (mar→may) + bitácoras/QA de un solo uso — candidatos a subcarpeta de archivo |

---

## 6. Higiene del repositorio

- **Tag residual `v1.0.0`** apuntando a un commit de marzo (Release 1), pusheado a origin. No tiene GitHub Release asociada (el auto-update lee releases, no tags), pero es confuso y conviene borrarlo (local + origin).
- **Rama `production`** congelada en `51df4ee` (2026-03-26), 300 commits por detrás de `main`. Decidir si se actualiza o se elimina la estrategia de rama estable.
- **`docscan_local_agent/`** en la raíz: directorio huérfano con solo `__pycache__` (bytecode del agente web sin fuentes). Borrar.
- **Infra web en la raíz**: `docker-compose.yml`, `Dockerfile.web`, `docker-entrypoint.sh`, `docker-bootstrap-db.py`, `requirements-web.txt`, `.dockerignore` — mover a `web/` o dejar documentado que pertenecen a la parte archivada.
- **`.gitignore`**: faltan `.coverage`, `.pytest_cache/`, `.ruff_cache/`. Limpiar `docscan.db` vacío de la raíz. Sin artefactos de build trackeados (limpio).
- **Venv**: estaba roto (una actualización del SO eliminó los binarios) — regenerado hoy con Python 3.14.6 y requirements al completo.
- **Dependencias desactualizadas** (además de las vulnerables): anthropic 0.84→0.117 (usada por los asistentes IA — revisar breaking changes), PySide6 6.10.2→6.11.1, opencv 4.13→5.0 (major), SQLAlchemy 2.0.48→2.0.51, cryptography 46→49.

---

## 7. Plan de acción propuesto (priorizado)

**P0 — inmediato**
1. Fix `main.py:119` (`get_scanner` → `create_scanner`) + test que cubra `--direct-mode`.
2. Actualizar Pillow a 12.3.0 (+ pydantic-settings 2.14.2, pytest 9.0.3) y pasar la suite.

**P1 — corto plazo**
3. Barrido ruff (check --fix + format) en commit propio.
4. Eliminar `app/providers/` (o migrar los asistentes IA a usarlo) — decisión de diseño.
5. README (versión/tests), CHANGELOG (separar `[Unreleased]` web), borrar `docscan_local_agent/`, ampliar `.gitignore`.
6. Borrar tag `v1.0.0` (local + origin).
7. Workflow de CI para tests+lint del desktop en push/PR.

**P2 — cuando toque**
8. Resolver TODO del webhook en `worker_main.py`.
9. Renombrar `test_executor.py`/`test_pipeline_worker.py` o fijar `testpaths`.
10. Subir cobertura de `workbench_window.py` y `scanner_config_dialog.py`.
11. Migrar estilos inline a QSS con propiedades dinámicas.
12. Actualizar/archivar `INFORME_PROYECTO.md`; ordenar `docs/`; decidir rama `production`.
13. Evaluar upgrades mayores (PySide6 6.11, opencv 5, anthropic 0.117).

Con P0+P1 cerrados, el proyecto queda listo para taggear una **v0.1.3** limpia
como base de la nueva etapa exclusivamente desktop.
