# Panel derecho del Workbench — cómo funciona en FlexibarNET 10 y diseño para DocScan

**Fecha:** 2026-10-26
**Fuente:** FlexibarNET 10 v1.30. Revisado en:
- el manual (`04-workbench.md` §«Panel derecho» y `06-configurator/01-general.md`
  §«Pestañas del Workbench»);
- `WorkbenchWindow.xaml` (líneas 607-953);
- `WorkbenchTabsLayout.cs`;
- `WorkbenchViewModel.{Barcodes,BatchFields}.cs`;
- `WorkbenchWindow.Barcodes.cs`.

**Requisito:** paridad funcional con Flexibar ([[project_paridad_flexibarnet10]]).

---

## 1. Cómo funciona en FlexibarNET 10

El panel derecho apila, de arriba abajo, **cuatro filas**:

| Fila | Qué es | Alto | Cuándo se ve |
|---|---|---|---|
| 0 | **Zona del separador** | Según contenido | Solo si la página enfocada es separador |
| 1 | **Panel «BARCODES DE LA PÁGINA · N»** | Según contenido, **tope de 280 px** con scroll | Si la App no lo oculta |
| 2 | **Panel «CAMPOS DE LOTE · N»** | Según contenido, **tope de 180 px** con scroll | Si la App no lo oculta **y** tiene campos definidos |
| 3 | **Pestañas** Verificación / OCR / Log | El resto del alto (mínimo 150 px) | Las que la App tenga visibles, en su orden |

Si la App oculta las tres pestañas, el bloque se colapsa: no queda una caja vacía.

### 1.1 Panel de barcodes

**Cabecera:** el título en versalitas con el número de códigos, el botón verde **«+ Añadir»** y
un chevron ⌃/⌄ que pliega o despliega la lista. El plegado dura lo que la sesión.

**Una fila por código** (no una tabla):
- un punto de color de 14 px, el mismo color que su recuadro en el visor;
- el **valor** en monoespaciada, en seminegrita y recortado con «…» (el tooltip muestra el
  valor completo);
- debajo, en pequeño, «simbología · motor · **rol** (en azul)» y un distintivo naranja
  **MANUAL** si se añadió a mano;
- a la derecha, botones por fila: marcar área y **eliminar** (papelera roja).

**Comportamiento:**
- Pasar el ratón por una fila resalta su recuadro en el visor, y al revés: el recuadro
  resalta su fila.
- Añadir: «+ Añadir», **Ctrl+N** o **Insert**. Abre un diálogo validado con
  `ManualBarcodeRegex`; «Aceptar» queda deshabilitado hasta que el valor es válido.
- Eliminar: la papelera de la fila, o **Supr** con la fila enfocada.
- **Ctrl+Z** deshace la última edición de barcodes.
- La App puede ocultar «+ Añadir» (`HideAddBarcodeButton`). Si lo hace, también quedan
  desactivados sus atajos.

### 1.2 Panel de campos de lote

- Es **un panel**, no una pestaña. Lleva el mismo chevron de plegar.
- Cada campo muestra su nombre en seminegrita y su tipo en pequeño debajo; a la derecha,
  el control según el tipo.
- No aparece si la App no tiene campos, aunque esté marcado como visible.

### 1.3 Pestañas

- **Verificación:** el panel de verificación de la App. Si no tiene, muestra un texto
  centrado («Verificación avanzada no configurada»). Con el lote vacío muestra un aviso
  en lugar del panel.
- **OCR:** el texto OCR de la página enfocada, de solo lectura.
- **Log:** el log de la aplicación en monoespaciada de 11 px.
- **Pestaña inicial:** la que indique `DefaultTab` de la App. Si no indica ninguna, o
  indica una oculta, se abre la primera visible.

### 1.4 Configuración por App

En **Configurador → General → «Pestañas del Workbench»** hay una lista con casilla de
visibilidad y botones ▲▼ para las cinco entradas:
- **Barcodes** y **Campos** son paneles fijos arriba y en ese orden: se pueden ocultar,
  pero no reordenar.
- **Verificación**, **OCR** y **Log** se pueden ocultar y reordenar.

Se guarda en `App.WorkbenchTabsLayoutJson`. Si está vacío o no es válido, se usa el
orden por defecto con todo visible. Las entradas desconocidas se ignoran y las que falten
se añaden como visibles.

Ocultar un panel no desactiva lo que hay debajo: el pipeline sigue leyendo códigos y
haciendo OCR.

---

## 2. Cómo está hoy en DocScan

| Aspecto | DocScan hoy | Evidencia |
|---|---|---|
| Barcodes | `QGroupBox` con una **tabla** de 5 columnas (punto, Valor, Simbología, Motor, Rol), los botones «+ Barcode manual» y «− Barcode», y menú contextual | `barcode_panel.py:74-124` |
| Contadores del lote | Grupo propio entre los barcodes y las pestañas (Flexibar no lo tiene) | `barcode_panel.py:124` |
| Campos de lote | **Pestaña «Lote»**, no panel | `metadata_panel.py:70` |
| Pestañas | Lote, Verificación (si hay panel) y Log. **No hay pestaña OCR** | `metadata_panel.py:53-76, 245` |
| ⚠️ OCR, errores de procesado y de script de la página | **No se muestran nunca**: `set_verification_data` es un stub vacío | `metadata_panel.py:223-231` |
| ⚠️ Pestaña inicial | **Se ignora** `default_tab`: `set_default_tab` siempre va a la primera | `metadata_panel.py:233-235` |
| Fila ↔ recuadro del visor | Sin enlace | — |
| Plegar paneles | No | — |
| Visibilidad y orden por App | No existe | — |
| Atajos Insert / Supr / Ctrl+Z en barcodes | No | — |
| Distintivo MANUAL | No (el motor del código manual es `"manual"`, pero no se distingue) | `workbench_window.py:2009` |

Los dos ⚠️ son de la misma familia que el lote 3. Desde ese lote, un script que falla deja
la página «a revisión» con el motivo, **pero el Workbench no enseña ese motivo en ningún
sitio**: el operador ve el borde rojo y no sabe por qué.

---

## 3. Diseño para DocScan (paridad)

1. **Pila del panel derecho:** zona de separador (vacía hasta el lote 6), panel de
   barcodes, panel de campos y pestañas, con los mismos topes (280 y 180 px) y el mismo
   reparto del alto.
2. **Panel de barcodes:**
   - Una lista de filas en lugar de la tabla, con cabecera «BARCODES DE LA PÁGINA · N»,
     «+ Añadir» en verde, chevron, papelera por fila y distintivo MANUAL.
   - Hover fila ↔ recuadro en los dos sentidos.
   - Insert y Ctrl+N para añadir, Supr para eliminar.
   - Ctrl+Z para deshacer, con una pila de deshacer de la sesión, como el
     `BarcodeSession` de Flexibar.
   - «Marcar área» queda fuera: necesita el modo dibujo del visor, que DocScan no tiene.
3. **Panel de campos de lote:** lo que hoy es la pestaña «Lote» pasa a panel plegable,
   con el nombre y el tipo de cada campo.
4. **Pestañas Verificación / OCR / Log:**
   - **Nueva pestaña OCR** con el texto de la página.
   - **Implementar de verdad** `set_verification_data`, sin stub, y `default_tab`.
   - Los errores de script y de procesado de la página se ven en el Log, como en Flexibar,
     y como motivo junto a la página «a revisión».
5. **Configuración por App:**
   - Columna nueva `workbench_layout_json` con una migración Alembic aditiva. Se prueba
     antes sobre una copia de la BD real, comparando `COUNT(*)`.
   - Lista «Pestañas del Workbench» en Configurador → General, con casillas y ▲▼.
   - Casilla «Ocultar el botón de añadir barcode».
   - Las dos viajan en la exportación de la App. El test de columnas obliga a
     clasificarlas.
6. **Contadores del lote:** Flexibar no los tiene; DocScan sí, y son útiles. **Propuesta:**
   pasarlos a la **barra de estado**, como el «Procesado 5/5» de Flexibar, y liberar el
   panel derecho. Es la única desviación de la paridad, y la decides tú.

> ✅ **Implementado el 2026-10-26** (rama `feat/rediseno-ui`), con la decisión de
> llevar los contadores a la barra de estado. «Marcar área» sigue fuera, y la zona
> del separador llegará con el lote 6.

**Orden de implementación:**
1. Puntos 4 y 3, que corrigen los stubs.
2. Punto 2.
3. Punto 5.
4. Punto 6.

Cada paso con tests y capturas reales en los dos temas.
