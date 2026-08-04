---
name: Próxima sesión — Listado de pruebas manuales
description: El usuario pide al cerrar el 2026-04-25 que la próxima sesión arranque con un listado completo de pruebas manuales de todas las capacidades del proyecto hasta ahora (desktop + web). El listado va a ser el primer entregable del día siguiente.
type: project
originSessionId: 987692a1-907f-4d46-9768-1f49d37119a9
---
## Petición explícita del usuario (2026-04-25 al cerrar)

> "El próximo día me gustaría tener un listado de pruebas manuales de todas
> las capacidades hasta ahora."

Es la **prioridad 1 del próximo arranque**. No es desarrollo de features, es
documentación de QA. El destinatario es el propio usuario / el jefe — para
poder pasar la app a un tester o ejecutar el QA antes de release v0.1.1 con
instaladores.

## Alcance del listado a producir

Cubrir **todas** las capacidades implementadas hasta hoy. Es decir:

### Desktop (PySide6, rama main, v0.1.0 publicada + cambios de v0.1.1 en feature/web)
- Launcher: listar/crear/duplicar/borrar aplicaciones, init_global script.
- Configurador: las 6 pestañas (General, Imagen, Pipeline, Eventos, Transfer,
  BatchFields).
- Workbench desktop: escaneo SANE/import, pipeline completo (image_op,
  barcode, ocr, script), navegación, zoom, transferencia, eventos lifecycle
  (incluyendo los dos nuevos `on_batch_loaded` / `on_page_changed`),
  VerificationPanel.
- Batch manager: listado, abrir, borrar, exportar.
- DocScan worker (modo headless): folder watcher.
- Migraciones alembic.
- Cifrado de secrets (Fernet).

### Web (rama feature/web, sub-proyecto Workbench web cerrado en Fases 1-4)
- **Auth**: login, logout, registro, invitaciones, expiración, cambio de rol,
  multi-tenant.
- **Aplicaciones**: CRUD, pipeline editor, eventos.
- **Lotes**: lista, crear, abrir, upload, run pipeline, transfer, export ZIP,
  delete, reorder, delete-after, reprocess de página.
- **Workbench web Fases 1-4**:
  - Fase 1: tema claro/oscuro/auto (Catppuccin dual, ThemeSelector).
  - Fase 2: layout multi-panel (vue-splitpanes), 6 componentes view-only.
  - Fase 3: rotación, overlays fields, edición barcodes, menú contextual
    miniaturas, drag-drop reorder, tab Log, bloqueo UI durante run.
  - Fase 4: 5 eventos lifecycle (on_batch_loaded, on_navigate_*,
    on_page_changed, on_key_event), 16 shortcuts de teclado, modal
    cheatsheet, endpoint reprocess, filtros de foco.
- **Páginas**: PATCH metadatos, rotate, barcodes CRUD, exclusión, marcado
  para revisión.
- **WebSocket**: progreso pipeline, progreso transfer, eventos en vivo del log.

## Estructura sugerida del documento

`docs/MANUAL_QA.md` (o similar, decidir nombre con el usuario al arrancar).

Por cada capacidad:

```markdown
### [Categoría] Capacidad X

**Precondición**: ...
**Pasos**:
1. ...
2. ...
**Resultado esperado**: ...
**Endpoints/eventos involucrados**: ...
```

Idea: agrupar por flujo de usuario (no por componente técnico) para que sea
ejecutable de un tirón:

1. Bootstrap: instalación, primera ejecución, login.
2. Crear y configurar aplicación (cubre las 6 pestañas).
3. Crear lote, escanear/importar páginas.
4. Procesar lote: pipeline + cada tipo de step.
5. Trabajar en Workbench (desktop): navegación, edición, eventos, scripts.
6. Trabajar en Workbench (web): los mismos casos + tema, shortcuts, log.
7. Transferir lote.
8. Multi-tenant: aislamiento entre orgs.
9. Errores y edge cases: 401, 404, 409, scripts con bug, page con barcodes
   inválidos, etc.

## Inputs útiles para arrancar el día

- **CHANGELOG.md** — referencia de qué se ha entregado por release.
- **REQUIREMENTS.md** — los requisitos funcionales originales.
- **docs/INFORME_PROYECTO.md** — visión global.
- **docs/progreso_*.md** — historial de qué se ha hecho cada día.
- **CLAUDE.md** — arquitectura del pipeline, eventos lifecycle, scripts.
- **MEMORY.md** — patrones aprendidos, decisiones de diseño, follow-ups.

## Sugerencia de método

1. Brainstorm corto al arrancar para acordar nivel de detalle (¿una página
   resumen o checklist exhaustivo de 200 casos?).
2. Recorrer CHANGELOG cronológicamente y por release marcar las capacidades
   verificables.
3. Cruzar con REQUIREMENTS.md para no perder ningún UI-XX o requisito
   funcional original.
4. Producir `docs/MANUAL_QA.md` (o el nombre que el usuario elija).
5. Commit + push del documento. Nada de código en esta sesión salvo bugs
   triviales que se encuentren al revisar.

## Estado del repo al cierre de 2026-04-25

- Rama `feature/web` pusheada al remote, 4 commits funcionales + 1 informe
  desde `7dfa9f1` (cierre de Fase 4 ayer).
- Tests: **849 desktop + 191 backend + 359 frontend = 1399 passing**, 0
  fallos.
- Stack local sin levantar (Postgres docker, uvicorn, vite todos parados).

## Comandos útiles para arrancar

```bash
# Activar entorno
source .venv/bin/activate

# Levantar stack completo si es necesario para validar pasos del manual
docker start docscan-pg
uvicorn web.api.main:create_app --factory --reload --port 8001
cd web/frontend && npm run dev
```

## Usuarios de prueba en Postgres local

- `demo2@demo.com / demo12345` — company_admin, tenant "Demo Org".
- `colaborador@demo.com / colabpass1234` — operator del mismo tenant.
- `other@tenant.com / otherpass123` — admin de "Other Org".

## App de prueba en BD

- App id 8 "Pipeline Test v1" con pipeline de 5 steps que cubre los 4 tipos.
