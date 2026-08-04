---
name: web-saas-archivado
description: "Web SaaS ARCHIVADA el 2026-07-21 por decisión del usuario. Estado congelado de ramas, sprints y BD docker, y cómo retomar si algún día se reactiva."
metadata: 
  node_type: memory
  type: project
  originSessionId: 78f5f7b3-cd04-4f50-96e8-a6172a36063e
  modified: 2026-07-21T15:47:13.424Z
---

# Web SaaS — ARCHIVADO (2026-07-21)

El usuario decidió el 2026-07-21 **archivar la versión web SaaS** y focalizarse
en **DocScan Desktop**. Nada se borró: todo el trabajo está pusheado a origin.

## Estado congelado de ramas

- **`main`**: contiene la web SaaS completa mergeada el 2026-05-05 (`61fdb47`,
  merge --no-ff de `feature/web`, 279 commits). El desktop no cambió desde v0.1.2.
- **`feature/local-agent-d`** (aparcada, pusheada): HEAD `06a65ce`, 10 commits.
  Sprint D hito 13 (opciones de escaneo dinámicas) cerrado a nivel de código
  backend+frontend, pero **smoke real Canon DR-M160 incompleto** (paso 9 de 15).
  Hitos 14-17 (transfer scripts en cliente, built-ins db/pdf, tag v0.2.0)
  **nunca se hicieron**.
- **`feature/local-agent`** (mergeada en la -d): HEAD `28f70c5`, sprint cliente
  local fase 1 cerrado 2026-05-08.
- **`feature/web`**: HEAD `e658dc3`, ya mergeada a main.

## Estado al archivar

- Tests: 1882/1882 (869 desktop + 340 backend web + 127 agente + 546 frontend).
- Sin tag v0.2.0 — quedó condicionado a cerrar el sprint D.
- Bug conocido pendiente: [[project_workbench_stale_state_bug]]
  (WorkbenchView no recarga state al navegar entre lotes; workaround F5).
- BD docker de pruebas: [[project_bd_docker_estado]] (tenant TecnoMedia,
  operario@tecnomedia.es / <REDACTADO — ver gestor de contraseñas>, app AppHito7, MinIO bucket docscan).

## Cómo retomar (si algún día se reactiva)

1. Leer [[project_sprint_d_local_agent]] y `project_next_session_resume.md`
   histórico (los pasos 10-15 del smoke están en
   `docs/progreso_2026-05-11.md` § "Pendientes del smoke para la sesión siguiente").
2. `git checkout feature/local-agent-d` + `docker compose up -d` +
   `docker compose exec api alembic upgrade head` (HEAD alembic `e6f9a013c245`).
3. Agente local en :47816, frontend dev en :5173.
4. Cerrar smoke → fix bug stale state → hitos 14-17 → tag v0.2.0.

## Memoria relacionada (histórico web, mantener como archivo)

[[project_sprint_local_agent]], [[project_sprint_superadmin]],
[[project_web_version_plan]], [[project_roadmap_post_qa]],
[[project_objetivo_saas_portfolio]], [[project_web_session_next]]

## Aprendizajes web que siguen siendo útiles (resumen)

- ARQ 0.28.0 (no 0.26.3) para Python 3.14; pytest-asyncio 1.3.0 con pytest 9.
- 404 unificado para errores cross-tenant (no revelar existencia de recursos).
- `aria-modal="true"` como señal binaria para bloquear atajos con modal abierto.
- splitpanes emite `{event, panes}` (no array); jsdom necesita mock de ResizeObserver.
- Los detalles de sesiones QA/fixes web están en `docs/progreso_*.md` y
  `docs/qa_web_2026-04-27.md` del repo, y en el historial git.
