---
name: project_propuestas_flexibarnet10
description: Análisis de FlexibarNET10 (v1.11.0) como fuente de mejoras para DocScan — informe en docs/propuestas_desde_flexibarnet10_2026-07-27.md
metadata: 
  node_type: memory
  type: project
  originSessionId: 27894c49-5636-4cae-b9eb-e82cec45ee87
  modified: 2026-07-27T15:57:50.757Z
---

El 2026-07-27 analicé el repo hermano **`Tecnomedia/FlexibarNET10`** (privado, .NET 10 +
WPF + Vintasoft, **v1.11.0**, en producción real) para extraer propuestas de mejora para
DocScan. Resultado en **`docs/propuestas_desde_flexibarnet10_2026-07-27.md`**.

**Cómo acceder al repo**: NO existe clon local permanente (Nicolás lo desarrolla en su
laptop Windows). Usar `gh repo clone Tecnomedia/FlexibarNET10 -- --depth=50` en scratchpad.
`gh` está autenticado y tiene acceso. La fuente de verdad de su estado es
`docs/changelog.md`; su `docs/auditoria-paridad-docscan.md` está **congelado en v0.3.4** y
va en dirección contraria — no usarlo.

**Top propuestas** (detalle y priorización en el informe):
1. Caché de scripts por **contenido**, no por `step.id` — DocScan tiene el bug latente que
   Flexibar corrigió en #153 (`app/services/script_engine.py:57,85,138`).
2. Separador como propiedad de `Page` (`separator_value`), disociado de los barcodes →
   desbloquea documento lógico y transferencia por documento.
3. Launcher tipo hub: icono/color por app, etiquetas derivadas de la config, grupos
   colapsables.
4. Transferencia asíncrona en cola (ojo: idempotencia al encolar + cargar los eventos de la
   app también en el worker).

**Verificado que DocScan YA tiene** (no proponer): overlay de barcodes con paleta +
overlay de campos con etiqueta (`document_viewer.py:150-210`), contadores de lote, IA,
doble motor barcode, multiplataforma, worker headless, notificaciones.

**No portable** (no insistir): JBIG2/JPEG2000/PDF MRC (licencia Vintasoft), motor OMR +
diseñador, licenciamiento Keygen/AdminWeb, Tienda de Apps.

**Patrón útil**: para comparar estética generé capturas reales de DocScan con el script de
smoke headless (ver [[project_next_session_resume]] y la nota de validación en campo);
hay que llamar a `ThemeManager().apply_theme(Theme.DARK)` e importar todos los módulos de
`app/models/` a mano, porque `app/models/__init__.py` está vacío.
