---
name: project_lotes_flexibarnet_ejecutados
description: "Lotes 1 y 2 del informe FlexibarNET ejecutados, mergeados y publicados como v0.1.6 el 2026-07-28."
metadata: 
  node_type: memory
  type: project
  originSessionId: 3a574282-e6b0-4206-b4f4-4b8af65e1b75
  modified: 2026-07-28T10:12:42.222Z
---

**Lotes 1 y 2 de [[project_propuestas_flexibarnet10]] cerrados el 2026-07-28**:
mergeados a `main` vía **PR #1** (merge commit `2de8c0f`) y publicados como
**v0.1.6** (`6d147df`). Tests: 883 → **937 verdes**.

Hecho: caché de scripts por hash del fuente (C1) · salto directo a página en el
contador del visor (B9) · escritura atómica `app/utils/atomic_io.py` (C4) ·
borrado en disco diferido a `after_commit` (C5) · curación de ids de paso al
deserializar (C8) · regex de usuario acotadas `app/utils/safe_regex.py` (C3) ·
cancelación honesta en ScanWorker/RecognitionWorker (C7) · `ImageOpStep.persist`
opt-in (C9) · worker desatendido persiste la imagen procesada (antes nunca lo
hacía) · `app/models/__init__.py` importa todos los modelos (cierra el quirk de
aislamiento ORM: los tests sueltos ya corren).

**Decisiones cerradas** (estaban abiertas, resueltas por delegación del usuario):
- Dependencia **`regex` aceptada** (2026.7.19). Verificado que PyInstaller la
  empaqueta entera: módulos Python en el PYZ, `.so` nativo en `_internal/regex/`.
- **`replace_image()` NO se toca**: persiste el estado final del pipeline, no la
  imagen del script. Se documentó el comportamiento real en el docstring y en
  `docs-web/reference/scripting-api.md` en lugar de alinear el código, para no
  cambiar la salida de apps desplegadas.

**C2 verificado y NO aplica** a DocScan: los servicios no retienen configuración.
Fijado con tests; no reabrir.

**Pendiente y solo lo puede hacer el usuario**: validar la v0.1.6 instalada con el
escáner Canon DR-M160 (arrastrado desde la v0.1.5).

**Siguiente lote propuesto** (sin empezar): release temática de «separación de
documentos y launcher» — tarjetas con icono/color + grupos plegables (B2+B3) y
separador como propiedad de la página con documento lógico y transferencia
documento a documento (A1+A2). A1+A2 toca el modelo de datos: planificar antes.
