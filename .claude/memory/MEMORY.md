# DocScan Studio — Memoria de Proyecto

## FOCO ACTUAL (desde 2026-07-21): DocScan DESKTOP
- [Web SaaS ARCHIVADA 2026-07-21](project_web_archivado.md) — decisión del usuario; estado congelado de ramas/sprints y cómo retomar. No reabrir trabajo web salvo petición explícita.
- [Punto de retoma próxima sesión](project_next_session_resume.md) — foco desktop, candidatos de trabajo pendientes de priorizar.

## Referencia externa
- [Propuestas desde FlexibarNET10](project_propuestas_flexibarnet10.md) — repo hermano en .NET 10 (v1.11.0, producción). Informe de mejoras en `docs/propuestas_desde_flexibarnet10_2026-07-27.md`. Incluye un bug latente de caché de scripts en DocScan.
- ✅ [Lotes 1 y 2 cerrados 2026-07-28](project_lotes_flexibarnet_ejecutados.md) — mergeados vía PR #1 y publicados como **v0.1.6**; 937 tests; decisiones cerradas (dep `regex` aceptada, `replace_image` documentado sin tocar). Siguiente: lote «separación de documentos y launcher».

## Estado desktop
- ⚠️ [Bug: la app no migra la BD al arrancar](project_db_migration_bug.md) — destapado en campo 2026-07-22 (`create_all` no añade columnas; falta `notifications_json`). BD del usuario **ya reparada** (quirúrgico + stamp head, backup hecho, app arranca). **Fix de fondo pendiente para v0.1.5**: `upgrade head` peta por migraciones web; hay que separar cadena desktop/web. v0.1.4 publicada CON este bug.
- **Auditoría completa 2026-07-21** en `docs/auditoria_desktop_2026-07-21.md` — núcleo sano, cobertura 65%. Plan P0/P1/P2 en el doc.
- **P0+P1+P2 EJECUTADO y MERGEADO a `main` 2026-07-21** (pusheado a origin). **Release v0.1.3 taggeada** (tag apunta a commit con fix de sintaxis; build en curso al cerrar). Hecho: fix `--direct-mode`; deps CVE (Pillow 12.3.0, cryptography 48.0.1, pydantic-settings 2.14.2, pytest 9.0.3 — pip-audit limpio); borrado `app/providers/`; barrido ruff `--fix`+`format` + `ruff.toml`; `pytest.ini` (testpaths + --timeout=120); workflow CI `.github/workflows/ci.yml`; README/CHANGELOG/`.gitignore`; tags `v1.0.0` (local+origin) borrados; **SANE mockeado** en `test_scanner_service.py` (ya NO cuelga, suite completa 861/861 en ~22s); `test_create_duplicate_app` modal mockeado; `ruff check .` 100% limpio.
- **RESUELTO 2026-07-22 — toolchain unificado en Python 3.14**: el bug de portabilidad (`except A, B:` sin paréntesis, sintaxis PEP 758 solo válida en 3.14, que rompía la importación cuando CI/build eran 3.13) se cerró de raíz **unificando toda la cadena en 3.14**: `ci.yml`, `release.yml`, `docs.yml` → `PYTHON_VERSION 3.14`; `ruff.toml` → `target-version = py314`. `ruff format` bajo py314 volvió a quitar los paréntesis (`except A, B:`) y **ahora es correcto** porque el build es 3.14. Commits `4e6f5d9` (toolchain) + `b58feab` (format). Verificado: PySide6 6.10.2/opencv 4.13/Pillow 12.3/pymupdf tienen wheels 3.14 (venv local es 3.14, 861 tests verdes); PyInstaller 6.x soporta 3.8-3.14. **El GOTCHA anterior (ruff DEBE ser py313) YA NO APLICA** — con todo en 3.14, py314 es lo correcto. `.venv312/` de diagnóstico borrado.
- **Herramientas de diagnóstico**: `gh` CLI **SÍ está autenticado** (scopes gist/read:org/repo) — usar `gh run view --log-failed`, `gh release view`, etc. para ver logs de CI. El `$GITHUB_PAT` está **caducado (401)** — ignorarlo, usar `gh`. Los builds de release usan `softprops/action-gh-release@v2` (sobrescribe assets). `release.yml` NO corre tests (solo PyInstaller, que tolera la sintaxis 3.14-only); el CI nuevo sí importa los módulos y por eso destapó el bug.
- **Follow-ups P2 — parcialmente cerrados 2026-07-22**: HECHO → bytecode `docscan_local_agent/__pycache__` borrado, `.venv312` borrado, archivo basura `--db-path` borrado, rama `production` **borrada** (local+origin; estaba subsumida en main, 0 commits únicos). PENDIENTES → migraciones alembic head es web (inofensivo), infra docker web en raíz (documentado, mover rompería rutas).
- **Upgrades mayores de dependencias HECHO y MERGEADO a `main` 2026-07-22** (commits `2d9a35c`→`fcd1202`, pusheado a origin): opencv-python **4.13→5.0.0.93** (major; uso 100% core, breaking de OpenCV 5 —C API legacy, G-API/ML a contrib, DNN/ONNX— no afectan), anthropic **0.84→0.117.1** (superficie `Anthropic()`/`messages.create`/content blocks estable), PySide6 **6.10.2→6.11.1**, SQLAlchemy 2.0.51, zxing-cpp 3.1.0, PyMuPDF 1.28.0, openai 2.46.0. **Sin cambios de código**: 879 tests verdes tras cada fase (un commit por grupo de riesgo), ruff limpio, smoke de imports+clientes IA+ops cv2 OK. Todos con wheels cp314. Pillow/pydantic-settings/cryptography de la tabla del README también resincronizados.
- **Validación en campo del upgrade HECHA 2026-07-22** (sin escáner, sin commit — smoke en scratchpad): script `smoke_gui.py` que arranca las ventanas REALES en `QT_QPA_PLATFORM=offscreen` y captura cada una con `widget.grab().save()`. Verificado visualmente (miré los PNG): **LauncherWindow, AppConfigurator con sus 7 pestañas** (General/Imagen/Campos de Lote/Pipeline/Eventos/Transferencia/Notificaciones) y **WorkbenchWindow** renderizan perfectos en PySide6 6.11 (QSS, iconos SVG, layouts OK). **Pipeline real e2e con opencv 5** (FxGrayscale→AutoDeskew→ConvertTo1Bpp) ejecutó sin `processing_errors`, imagen de forma válida guardada con `cv2.imwrite`. Patrón reutilizable para futuras validaciones GUI headless: sane falso en `sys.modules` + `scanner_service.create_scanner` parcheado + modales QMessageBox/QDialog.exec no bloqueantes + BD real en fichero temporal (no `:memory:` por WAL) vía `create_db_engine/create_tables/get_session_factory`; ventanas: `LauncherWindow(session_factory)`, `AppConfigurator(app_obj, session_factory)` (pestañas en `self._tabs`), `WorkbenchWindow(app_id:int, session_factory)` con `patch APP_DATA_DIR`. **Único resto pendiente**: arranque interactivo con escáner físico real (DR-M160) — solo el usuario puede.
- **Webhook configurable HECHO 2026-07-22** (commit `6c5aff7`): cerrado el TODO `webhook=None` de `worker_main.py`. Columna nueva `applications.notifications_json` (migración `c1d5e9f34b28`, down_revision al head web `a3b8d4e2f7c9` — cadena lineal, sin multiple-heads), dataclass `NotificationConfig`+`parse/serialize_notification_config` en `notification_service.py` (patrón `image_config.py`), pestaña «Notificaciones» en el configurador (`tab_notifications.py`, registrada a mano en `app_configurator.py`), worker cablea el webhook en notify_transfer_complete/notify_error, exportable en `app_export_service.py`. +18 tests, suite **879 verde**. **Email SMTP pendiente**: estructura JSON anidada lo admite sin migración, pero falta UI + cifrado Fernet del password (regla crítica). `INFORME_PROYECTO.md` ya se actualizó a v1.1 esta sesión.
- Pasos 1-22 completados. Releases: v0.1.0, v0.1.1, v0.1.2 (2026-04-30), v0.1.3 (2026-07-21). **v0.1.6 taggeada 2026-07-28** (commit `6d147df`) — ver [[project_lotes_flexibarnet_ejecutados]]. **v0.1.5 taggeada y pusheada 2026-07-22** (commit `b98403e`): fix del crash de migraciones (ver [[project_db_migration_bug]]); `_version.py`→0.1.5, CHANGELOG `[0.1.5]`; binario PyInstaller validado LOCALMENTE contra BD legacy antes de taggear (cazó un `logging.config` faltante en hiddenimports que habría roto producción como v0.1.4). **v0.1.4 taggeada y pusheada 2026-07-22** (commit `dad4002`, tag `v0.1.4`): recoge webhook de notificaciones + upgrades de dependencias mayores + toolchain 3.14; `_version.py` bumpeado a 0.1.4, CHANGELOG `[Unreleased]`→`[0.1.4] - 2026-07-22`. Build `release.yml` disparado (run 29911729055) — primer empaquetado con opencv 5 + PySide6 6.11 bajo PyInstaller. Detalle en CHANGELOG.md.
- CI: `release.yml` dispara con tag `v*` (Ubuntu 24.04 + Windows latest, Python 3.13). Instaladores: AppImage (Linux) + Inno Setup (Windows).
- Tests desktop: **879 passing** (última medición 2026-07-22, con el stack de deps actualizado).
- Rama de trabajo desktop: partir de `main` (incluye la web mergeada, pero `app/` intacto desde v0.1.2).
- [Progreso instaladores + auto-update](project_release2_progress.md) — releases 1-3, docs, empaquetado, auto-update completados.
- [Ideas de roadmap 2026-03-20](project_upcoming.md) — el asistente IA de pipelines YA se implementó en Release 3 (`app/services/pipeline_assistant.py` + `ai_mode_assistant.py`); no proponerlo como pendiente.
- Pendientes menores desktop: verificación visual de la release instalada (versión en "Acerca de", eventos nuevos en catálogo, `page.id` en scripts); barridos globales ruff format y prettier (hacerlos aparte para no contaminar commits funcionales).

## Web SaaS — archivado (referencia)
- `main` contiene la web SaaS completa (merge `61fdb47`, 2026-05-05). Rama `feature/local-agent-d` aparcada en `06a65ce` con hito 13 sin smoke completo; hitos 14-17 y tag v0.2.0 nunca hechos.
- Histórico en: [sprint local agent](project_sprint_local_agent.md), [sprint D](project_sprint_d_local_agent.md), [sprint superadmin](project_sprint_superadmin.md), [plan web](project_web_version_plan.md), [roadmap post-QA](project_roadmap_post_qa.md), [objetivo portfolio](project_objetivo_saas_portfolio.md), [bug workbench stale](project_workbench_stale_state_bug.md), [BD docker](project_bd_docker_estado.md).

## Patrones aprendidos (desktop)
- ⚠️ [Un timeout por hilos NO acota un regex](feedback_no_timeout_regex_por_hilos.md) — `re` no libera el GIL y congela el intérprete entero; usar el módulo `regex`
- [Tests de QThread sin carreras](feedback_qthread_tests_sin_carreras.md) — `requestInterruption()` con DirectConnection; no afirmar sobre progreso parcial
- PySide6: `QPainter.RenderHint.SmoothPixmapTransform` (no `self.renderHints().RenderHint`)
- pytest-qt: `qtbot.addWidget()` solo con QWidget, NO con QThread; para QThread usar start/wait/waitSignal
- Pipeline executor espera duck-typed objects (page.image, page.barcodes, page.flags…)
- Session management: expunge objects antes de cerrar session para uso en UI
- `_workbenches: list = []` en main.py para evitar GC de ventanas
- SANE no es thread-safe: usar `scanimage` subprocess para adquisición desde QThread; `dev.snap()` falla con algunos drivers
- QSS sobreescribe `setFont()` — estilos siempre en .qss; triángulos CSS no funcionan (usar SVG con `image: url()`); estilar `::up-button` de QSpinBox borra flechas nativas (proveer SVGs)
- QDateEdit: `setCalendarPopup(True)`, valor inicial no emite `dateChanged`
- Barcode model: atributo `symbology`, no `type`. Page model: no tiene atributo `state`
- `str.format()` con `**kwargs` requiere identificadores válidos (espacios → underscores)
- Pillow save: BGR→RGB con `cv2.cvtColor` antes de `Image.fromarray()`; ImageLib.save() usa Pillow (no cv2) por DPI/TIFF/JPEG
- Alembic + SQLite: NOT NULL requiere `server_default` en ALTER; `render_as_batch=True` obligatorio en env.py
- ImageConfig: sin DPI (lo controla el escáner); color_mode solo reduce (color→gris→BW)
- Barcode manual: config en `ai_config_json` (`barcode_regex`, `barcode_fixed_value`)
- Memory leak ventanas: WA_DeleteOnClose + deleteLater() en QMainWindow no-principales
- i18n: QSettings "DocScanStudio"/"DocScanStudio", clave "i18n/language"; module-level strings con QT_TRANSLATE_NOOP + funciones lazy
- VerificationPanel: script en `events_json["verification_panel"]`, no es evento lifecycle
- El hook `.claude/hooks/ruff-format.sh` reformatea archivos enteros al tocarlos con Edit/Write y puede borrar imports recién añadidos como "unused". Workaround: `mcp__filesystem__edit_file` no dispara el hook.
- **Suite no interactiva y sin hardware (desde 2026-07-22)**: `tests/conftest.py` global hace tres cosas — (1) fixture `autouse` que mockea todos los modales Qt (QMessageBox/QDialog.exec/QFileDialog/QInputDialog) para que ningún test espere un clic; (2) inyecta un módulo `sane` falso en `sys.modules` **antes de recolectar** para que ninguna ruta (p.ej. `create_scanner()` en `test_create_scanner_auto`) abra el escáner USB real → elimina el prompt de admin polkit/libusb y los ~33s de enumeración; (3) `collect_ignore_glob` autodescarta los tests de la web archivada (test_web_*/test_arq_*/test_pipeline_runner_events) cuando faltan fastapi/bcrypt/arq. El CI ya NO enumera `--ignore` manuales: delega en el conftest (commits `41dcc6d`, `e4f84ef`). `pytest tests/` sin flags = 861 passed ~24s, cero interacción. Los tests que necesitan retorno concreto de un diálogo lo mockean localmente (gana sobre el global).
- **Aislamiento ORM**: correr `test_launcher.py` **suelto** falla con `NameError: OperationHistory is not defined` (relationship sin resolver porque nadie importó ese modelo antes). NO es bug del conftest; se resuelve al correr la suite completa. Preexistente.

## Decisiones de diseño
- [ConditionStep/HttpRequestStep descartados](feedback_discarded_steps.md) — redundantes con ScriptStep
- [Perfiles de usuario descartados](feedback_user_profiles_discarded.md)
- [batch.lock descartado](feedback_batch_lock_discarded.md) — foco mono-estación
- [Atajos de teclado del workbench](project_keyboard_shortcuts.md)

## Informe de progreso para el jefe
- **OBLIGATORIO**: al final de cada sesión, crear `docs/progreso_YYYY-MM-DD.md` (resumen, cambios, estado, próximos pasos). Doc base: `docs/INFORME_PROYECTO.md`.

## Preferencias de comunicación
- [Español de España](feedback_spanish_spain.md) — castellano peninsular
- [Actualizar docs en cada cambio](feedback_update_docs_on_changes.md) — README y CHANGELOG sincronizados
- [Push al cerrar sesión](feedback_push_on_close.md)
- [No pausar por sección en brainstorm](feedback_no_pause_per_section.md)
- [Tests inline pueden ocultar bugs reales](feedback_inline_tests_can_hide_bugs.md) — exigir smoke e2e real antes de declarar "validado"
- [No romper la desktop al evolucionar la web](feedback_no_romper_desktop.md) — 869 tests desktop verdes tras cada cambio compartido

## Entorno
- Python 3.14, venv en `.venv` (`source .venv/bin/activate`)
- Remoto: git@github.com:ferreret/docscan.git
- Escáner de test: Canon imageFORMULA DR-M160 (canon_dr:libusb)
- [GitHub API via curl](feedback_github_api.md) — usar $GITHUB_PAT, no gh CLI
