# Progreso 2026-03-26 (sesión 2) — Documentación + Auto-update

## Resumen

Sesión dedicada a completar la documentación con capturas de pantalla reales y comenzar la implementación del sistema de auto-actualización.

## Documentación completada

### Screenshots integrados (7 capturas reales)
- Launcher (tema oscuro), Workbench (completo), Configurador (pipeline, general, imagen, campos, eventos, transferencia), AI Mode, Gestor de Lotes, diálogos (nueva app, barcode, OCR, script), Acerca de
- README.md con 2 imágenes inline (launcher + workbench)
- Manual Word regenerado: 18 figuras reales, 1.2 MB
- MkDocs web: 0 TODOs pendientes, todas las imágenes integradas

### Publicación
- GitHub Pages publicado: https://ferreret.github.io/docscan/
- CHANGELOG.md con historial completo de releases

### Documentos de ejemplo
- `docs/generate_sample_docs.py`: genera 6 peticiones clínicas sintéticas con barcodes Code128

## Auto-actualización (Fase 1 completada)

### Versión centralizada
- `app/_version.py`: fuente única (`__version__ = "0.1.0"`)
- Actualizado: about_dialog, splash_screen, generate_manual

### UpdateService
- `app/services/update_service.py`: lógica pura sin Qt
  - `check_for_update()`: consulta GitHub Releases API, compara versiones
  - `download_update()`: descarga con progreso por chunks
  - `verify_checksum()`: SHA-256 contra SHA256SUMS.txt
  - `apply_update()`: Linux (reemplazar AppImage) / Windows (Inno Setup silencioso)
  - `_find_platform_asset()`: selección automática por plataforma

### Workers
- `app/workers/update_worker.py`: QThread wrappers
  - `UpdateCheckWorker`: señales update_available, no_update, check_error
  - `UpdateDownloadWorker`: señales progress, download_finished, download_error

### Tests
- 15 tests nuevos para update_service (mocks de GitHub API)
- Total: **828 tests passing**, 0 failed

## Plan pendiente (próximas sesiones)

### Fase 2: UI de actualización
- Diálogo de descarga con notas y progreso
- Banner de notificación en el Launcher
- Botón "Buscar actualizaciones" en Acerca de

### Fase 3-5: Empaquetado
- PyInstaller specs (Linux + Windows)
- AppImage + Inno Setup
- GitHub Actions CI/CD

### Fase 6: Informe de licenciamiento
- Documento ejecutivo para dirección
- Modelos de negocio, competencia, estrategia recomendada
