---
name: Progreso Instaladores + Auto-update
description: Estado de implementación de DocScan Studio — instaladores y distribución (2026-03-26)
type: project
---

## Releases completadas y mergeadas a main
- Release 1/1B: infraestructura, servicios, UI, ImageLib
- Release 2/2B: i18n, atajos, OCR estructurado, verificación
- Release 3: AI MODE, export/import, sidebar, detección blancos, splash

## Estrategia de ramas (2026-03-26)
- `main`: desarrollo
- `production`: rama estable para releases
- `feature/installers`: rama actual de trabajo (instaladores)

## Documentación — Completada (2026-03-26)
- README.md con screenshots reales en GitHub
- Manual Word: 12 capítulos, 18 figuras reales, 1.2 MB
- MkDocs Material: 13 páginas, publicado en https://ferreret.github.io/docscan/
- CHANGELOG.md con historial completo

## Auto-actualización — Fases 1-2 completadas (2026-03-26)
- Fase 1: `app/_version.py`, `app/services/update_service.py`, `app/workers/update_worker.py`
- Fase 2: `app/ui/update_dialog.py` (diálogo descarga+progreso), banner en launcher, botón en AboutDialog, auto-check en main.py
- Estilos QSS para banner en dark.qss y light.qss
- 21 tests nuevos para UI de actualización

## Empaquetado — Fases 3-5 completadas (2026-03-26)
- Fase 3: `build/docscan-linux.spec`, `build/docscan-windows.spec`
- Fase 4: `build/appimage/AppImageBuilder.yml` + `docscan.desktop`, `build/inno/docscan.iss`
- Fase 5: `.github/workflows/release.yml` (build-linux, build-windows, release)

## Fase 6: Informe de licenciamiento — Completada (2026-03-26)
- `docs/INFORME_LICENCIAMIENTO.md`: 10 secciones, análisis completo

### Estado técnico
- Tests: 849 passing (828 + 21 nuevos), 0 failed
- Rama: `feature/installers`
- Próximo paso: test manual PyInstaller en Linux, tag de prueba v0.1.0-rc1

**Why:** Tracking para continuar en próximas sesiones.
**How to apply:** Todo el plan de instaladores está implementado. Falta probar build real y primera release.
