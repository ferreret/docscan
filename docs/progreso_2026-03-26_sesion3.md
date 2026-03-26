# Progreso 2026-03-26 — Sesión 3: Instaladores, distribución y release v0.1.0

## Resumen

Implementación completa del plan de instaladores (Fases 2-6), pruebas de CI/CD,
verificación de instaladores en Linux y Windows, y publicación de la primera
release estable v0.1.0.

## Cambios realizados

### Fase 2 — UI de actualización
- `app/ui/update_dialog.py`: diálogo de descarga con notas de release, barra de progreso, verificación SHA-256
- `app/ui/launcher/launcher_window.py`: banner de actualización con botones Ver novedades / Actualizar / Ignorar
- `app/ui/about_dialog.py`: botón "Buscar actualizaciones" con feedback de estado
- `main.py`: auto-check en segundo plano al arrancar (UpdateCheckWorker)
- Estilos QSS en `dark.qss` y `light.qss` para el banner

### Fase 3 — PyInstaller
- `build/docscan-linux.spec`: hiddenimports completos, excludes Windows, modo onedir
- `build/docscan-windows.spec`: hiddenimports completos, excludes Linux, icono

### Fase 4 — Instaladores de plataforma
- `build/appimage/AppImageBuilder.yml` + `docscan.desktop`
- `build/inno/docscan.iss`: Inno Setup con español/inglés/catalán, modo silencioso

### Fase 5 — CI/CD
- `.github/workflows/release.yml`: trigger por tag v*, builds paralelos Linux+Windows, release con SHA256SUMS.txt

### Fase 6 — Informe de licenciamiento
- `docs/INFORME_LICENCIAMIENTO.md`: 10 secciones completas para dirección

### Infraestructura de ramas
- Rama `production` creada para releases estables
- Rama `feature/installers` para desarrollo (mergeada y eliminada)
- Flujo: feature/* → main → production + tag → CI/CD → Release

### Fixes durante CI/CD
- Python 3.14 → 3.13 (no disponible en setup-python)
- pytwain 2.6.0 → 2.3.0 (versión correcta en PyPI)
- LicenseFile comentado en Inno Setup (pendiente decisión de dirección)
- libgl1-mesa-glx → libgl1 (Ubuntu 24.04)

## Verificación
- Build PyInstaller Linux local: 539 MB, binario funcional
- AppImage desde GitHub Releases: 180 MB, verificado en Linux
- Installer Windows desde GitHub Releases: 101 MB, verificado en Windows
- 849 tests passing, 0 failed (21 nuevos para UI de actualización)
- CI/CD: 3 jobs verdes (build-linux 3m24s, build-windows 2m48s, release 19s)

## Releases publicadas
- v0.1.0-rc1: pre-release de prueba (CI/CD debugging)
- v0.1.0-rc2: pre-release verificada en ambas plataformas
- **v0.1.0**: release definitiva publicada

## Estado actual
- Rama `main` en `51df4ee`
- Rama `production` sincronizada con main
- Tag `v0.1.0` publicado con instaladores para Linux y Windows
- Email de comunicación preparado para dirección

## Próximos pasos
- Feedback de dirección sobre informe de licenciamiento
- Decisión sobre licencia del código fuente (MIT/Apache/propietaria)
- Pruebas funcionales completas en Windows (escáner, pipeline, transferencia)
- Iterar con feedback de usuarios
