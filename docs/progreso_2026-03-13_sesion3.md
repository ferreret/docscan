# Progreso — 2026-03-13 (Sesión 3: Tests manuales + mejoras UX)

## Resumen

Sesión de pruebas manuales de Release 1B y mejoras de UX/funcionalidad detectadas durante el testing.

## Tests manuales completados

| Sección | Test | Estado |
|---------|------|--------|
| 1.1 | Estructura de pestañas (6 tabs) | OK |
| 1.2 | Visibilidad condicional por formato | OK |
| 1.3 | Visibilidad condicional por modo color | OK |
| 1.4 | Rango de valores | OK (DPI eliminado) |
| 1.5 | Persistencia | OK |
| 2.1 | Escaneo JPEG calidad baja | OK |
| 2.2 | Escaneo TIFF con compresión | OK |
| 2.3 | Escaneo PNG | OK |

**Progreso: 8 de 59 tests completados (secciones 1 y parte de 2).**

## Mejoras de UX implementadas

### Estilos QSS (dark.qss + light.qss)
- **QCheckBox**: estilos explícitos (antes invisibles con temas custom)
  - Borde visible, fondo contrastado, checked = azul sólido, hover = borde azul, disabled
- **QSpinBox / QDoubleSpinBox**: estilados consistentes con QComboBox
  - `min-height: 24px`, `padding: 5px 10px`, botones up/down con fondo diferenciado
  - Flechas SVG personalizadas por tema (`resources/icons/arrow-{up,down}-{dark,light}.svg`)
- **Fecha en cards del launcher**: color más visible en ambos temas

### DPI eliminado de ImageConfig
- **Motivo**: el DPI lo determina el escáner; tenerlo en ImageConfig generaba metadatos incorrectos
- Eliminado de: `ImageConfig` dataclass, pestaña Imagen, `_save_with_config()`
- Tests actualizados (12/12 passing)

### Modo color — nota aclarativa
- Tooltip y nota informativa: "El modo color solo puede reducir (color→gris→B/N), no añadir color"

## Funcionalidades nuevas

### Clonar aplicación (Launcher)
- Botón "Clonar" en toolbar, duplica toda la configuración
- Nombre automático: "X (copia)", "X (copia 2)", etc.

### Aplicaciones inactivas
- Ordenación: activas primero en el listado
- Bloqueo: no se puede abrir workbench de app inactiva

### Barcode manual — configuración y ejecución
- **Pestaña General**: grupo "Barcode manual" con regex de validación y valor fijo
- **Workbench "+"**: inserta valor fijo o pide al usuario con validación regex
- **Workbench "−"**: elimina barcode seleccionado con confirmación
- Persiste como `Barcode(symbology="MANUAL", engine="manual")`

## Archivos nuevos (4)
- `resources/icons/arrow-{up,down}-{dark,light}.svg`

## Archivos modificados (13)
- `resources/styles/dark.qss` — QCheckBox, QSpinBox
- `resources/styles/light.qss` — QCheckBox, QSpinBox
- `app/models/image_config.py` — eliminado `dpi`
- `app/services/batch_service.py` — eliminado `dpi` en save
- `app/ui/configurator/tabs/tab_image.py` — sin DPI, notas actualizadas
- `app/ui/configurator/tabs/tab_general.py` — grupo Barcode manual, espaciado
- `app/ui/launcher/app_list_widget.py` — colores fecha
- `app/ui/launcher/launcher_window.py` — Clonar, bloqueo inactivas
- `app/ui/workbench/barcode_panel.py` — `selected_row()`, `selected_value()`
- `app/ui/workbench/workbench_window.py` — insertar/eliminar barcode
- `app/db/repositories/application_repo.py` — orden activas primero
- `tests/test_image_config.py` — adaptados sin `dpi`
- `docs/MANUAL_TEST_RELEASE_1B.md` — tests 1.1-2.3 marcados

## Próximos pasos
- Continuar tests manuales desde sección 2.4 (escaneo escala de grises)
- Secciones pendientes: 2.4-2.6, 3-15
- Probar funcionalidad de clonar app y barcode manual
