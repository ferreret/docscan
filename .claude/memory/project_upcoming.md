---
name: Próximas funcionalidades planificadas
description: Multilenguaje, pruebas Windows, release producción — decisiones de producto 2026-03-20
type: project
---

Decisiones tomadas 2026-03-20:

- **ConditionStep y HttpRequestStep descartados** — ScriptStep cubre ambos casos con skip_to() y httpx. Eliminados de CLAUDE.md.
- **Tests corregidos** — 673/673 passing, events_json unificado. Listo para release.

## Roadmap

### Release 1 (actual — merge inminente)
- Merge release_1 → main, tag, pruebas reales en producción
- Pruebas Windows (clonar repo en laptop, verificar TWAIN/WIA, paths, dependencias)

### Release 2
- **Multilenguaje** — Español (España), Inglés, Catalán. Qt i18n (QTranslator + .ts files)
- **Atajos de teclado** en workbench
- **Asistente IA para pipelines** — Construcción de pipelines por lenguaje natural para usuarios no técnicos. Investigar: usar Claude API para interpretar instrucciones en lenguaje natural y generar la lista de PipelineSteps + ScriptSteps correspondiente. Posible enfoque: chat embebido en el configurador que traduce "quiero leer barcodes Code128 y extraer el número de factura" a la secuencia de pasos.
- **Documentación completa** — Dos niveles:
  - Manual de usuario (instalación, uso del launcher, workbench, configurador)
  - Manual técnico/administrador (arquitectura, pipeline, scripts, API, despliegue)
- **Instaladores** — Crear paquetes distribuibles:
  - Linux: AppImage o .deb (PyInstaller/cx_Freeze + empaquetado)
  - Windows: .exe installer (PyInstaller + NSIS o Inno Setup)
- **Auto-actualización** — Publicar en GitHub Releases, la app consulta la API al arrancar, notifica y descarga nueva versión. Posible enfoque: PyUpdater o updater propio con GitHub Releases API.

**Why:** El usuario quiere estabilizar y publicar antes de añadir más features.

**How to apply:** Release 1 es estabilización. Release 2 agrupa las funcionalidades de usabilidad y distribución.
