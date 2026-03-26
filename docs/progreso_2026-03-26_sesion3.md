# Progreso 2026-03-26 — Sesión 3: Instaladores y distribución

## Resumen

Implementación completa del plan de instaladores (Fases 2-6): UI de actualización,
specs de PyInstaller, configuraciones de AppImage e Inno Setup, CI/CD con GitHub Actions
e informe de licenciamiento para dirección.

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

### Infraestructura
- Rama `production` creada desde main
- Rama `feature/installers` para desarrollo
- `.gitignore` actualizado para incluir ficheros de build

## Verificación
- Build PyInstaller Linux exitoso: 539 MB, binario funcional sin Python
- 849 tests passing, 0 failed
- 21 tests nuevos para UI de actualización

## Estado actual
- Rama `feature/installers` lista para merge a main
- CHANGELOG.md actualizado con entrada [0.1.0]

## Próximos pasos
- Merge a main
- Test en máquina Windows (Inno Setup)
- Tag v0.1.0-rc1 para probar CI/CD
- Primera release pública v0.1.0
