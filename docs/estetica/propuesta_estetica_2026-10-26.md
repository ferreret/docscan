# Propuesta de rediseño visual — paridad con FlexibarNET 10

**Fecha:** 2026-10-26
**Referencia:** FlexibarNET 10 v1.30 (`Themes/Palette.{Dark,Light}.xaml`, capturas del
manual). Se aplica el requisito de paridad con Flexibar.
**Comparativas:** `comparativa_launcher.png` y `comparativa_workbench.png` en esta
carpeta. Cada una muestra, de izquierda a derecha, DocScan hoy, un prototipo con solo
la paleta navy y la fuente Inter, y FlexibarNET 10.

---

## 1. Diagnóstico

Las capturas son de las ventanas reales, en offscreen y en los dos temas.

| # | Problema | Evidencia |
|---|---|---|
| 1 | **No hay una fuente única de color.** La paleta Catppuccin está repetida en dos QSS (22 y 28 colores) y, además, hay **92 colores fijos en el Python** (iconos, tarjetas, estados de página, barra del visor). Por eso cambiar de tema no recolorea medio interfaz | `resources/styles/*.qss`, `app/ui/**/*.py` |
| 2 | **Iconos hechos a mano**: unos 30 dibujados con `QPainter`, repartidos en 3 ficheros, con trazos y tamaños distintos. La barra del visor mezcla azul, naranja y rojo, con glifos poco legibles (`>|||`, `>!`, `1:1`) | `icon_factory.py`, `launcher/sidebar.py`, `workbench/viewer_overlay.py` |
| 3 | **Tipografía**: se pide «Segoe UI», que no existe en Linux, y se cae a Ubuntu o DejaVu. Hay 11 tamaños distintos (de 11 a 36 px); el contador `2 / 4` sale a 36 px y en rosa | `light.qss:7`, `dark.qss` |
| 4 | **Componentes con aspecto antiguo** | Ver la lista de abajo |

Componentes concretos:

- **Toolbar del Workbench:** radio buttons «Escáner / Importar» y botones de texto, con
  Transferir y Cerrar lote idénticos.
- **Tarjetas del launcher:** avatar gris con la inicial, sin etiquetas ni menú y con la
  fecha en ISO.
- **Configurador:** la lista de pasos pinta el estado como texto (`[✓] Imagen: …`).
- **Campo fecha:** el botón del calendario parece una casilla de verificación.
- **Tabla de barcodes:** cuando está vacía, muestra una columna fantasma y un scroll.
- **Barra de estado:** texto suelto, sin indicador.

**El prototipo de paleta lo confirma**: cambiar solo los colores del QSS mejora el
contraste, pero no la impresión general. Lo que envejece la interfaz son los iconos, la
toolbar y las tarjetas, que viven en el Python.

---

## 2. Propuesta (lógica de FlexibarNET 10)

### E1 — Paleta como fuente única

`app/ui/palette.py` con **las mismas claves que Flexibar**: `base`, `mantle`, `crust`,
`surface0-2`, `overlay0`, `subtext0`, `text`, `blue`, `green`, `red`, `yellow`, `peach`,
`orange`, `mauve`, `hover` y `danger_hover`.

- **Oscuro:** el navy de Flexibar (`#0d1422` / `#141d2f` / `#60a5fa`…), con su ajuste de
  legibilidad en `overlay0` y `subtext0`.
- **Claro:** el claro de Flexibar (`#fafbfc` / `#1e66f5`…).

Los QSS pasan a ser **plantillas** (`{surface0}`) que rellena el `ThemeManager`, y todo el
Python lee los colores de `palette`. Así, cambiar de tema recolorea todo, incluidos los
iconos.

### E2 — Un único juego de iconos

**Lucide** (licencia ISC): trazo fino, monocromo y el más parecido a los Segoe Fluent
Icons que usa Flexibar, que solo existen en Windows y no se pueden redistribuir.

- Se empaquetan unos 40 SVG en `resources/icons/lucide/`.
- Un helper `icon("scan", role="text")` los recolorea con la paleta mediante
  `QSvgRenderer` y los cachea por tema.
- Sustituye todos los iconos dibujados con `QPainter`.
- **Necesita descargar** el paquete `lucide-static`, que es MIT/ISC y pesa unos 2 MB de
  SVG.

### E3 — Tipografía

- **Inter** (OFL) empaquetada y registrada con `QFontDatabase`. Se toma del paquete
  `fonts-inter` de Ubuntu, sin descarga.
- En Windows se usa «Segoe UI», como Flexibar.
- La escala se reduce a **4 tamaños**: 12 / 13 / 15 / 22 px, más 28 para el título del
  launcher. El ajuste A+/A− se mantiene.

### E4 — Componentes, por orden de impacto

| Orden | Componente | Cambio (como Flexibar) |
|---|---|---|
| a | Toolbar del Workbench | «Escanear» como botón primario con icono, más ⚙ perfil. Además: «Importar…», «Procesar», **Transferir en verde** y **Cerrar lote en rojo**. Fuera los radio buttons (B5/B6). ✅ **Hecho** el 2026-10-26; como DocScan no tiene perfiles de escaneo, ⚙ lleva escáner, fuente y «mostrar opciones», y el distintivo dice «Escáner: …» |
| b | Barra del visor | Iconos monocromos del mismo trazo, contador normal `1 / 5` y el color reservado al estado: banderita naranja de separador y papelera roja (B7) |
| c | Tarjetas del launcher | Icono cuadrado con acento **derivado de la configuración** (12 iconos × 7 acentos, como el `AppIconCatalog` de Flexibar), hasta 3 etiquetas automáticas (`Códigos de barras`, `Scripts`, `PDF`), fecha localizada y menú ⋮ (B2). ✅ **Hecho** el 2026-10-26, con el mismo hash FNV-1a del nombre que Flexibar para el acento. Sin selector manual de icono (Flexibar lo tiene; aquí haría falta una columna nueva) |
| d | Barra de estado | Contador a la izquierda y «● Listo» a la derecha. En el Workbench, `Procesado 5/5` y `1240×1754 — 150 DPI` (B8). ✅ **Hecho** el 2026-10-26. Los DPI solo se muestran si la imagen guarda un valor real (≥ 50) |
| e | Panel derecho | Cabeceras en versalitas (`BARCODES DE LA PÁGINA · 1`), barcodes como lista con punto de color en lugar de tabla y campo fecha con su icono de calendario |
| f | Configurador | Lista de pasos con icono y color por tipo y casilla real de activo, como paso previo al master-detail |

### Fuera de esta ronda

- **Editor de pipeline master-detail (B4)**: es el cambio de interfaz más caro.
- **Grupos en el launcher (B3)**: necesitan un campo en el modelo de datos.
- **Zona de separador** en el panel derecho: va con el lote 6 (separadores).

---

## 3. Cómo se verifica

- Cada fase se cierra con **capturas antes/después de las ventanas reales**, en offscreen
  y en los dos temas. El script de captura se incorpora al repo como herramienta
  (`tools/ui_snapshots.py`).
- La suite completa queda en verde.
- **Revisión a ojo** de las capturas, contra Flexibar.
- La regla de `CLAUDE.md` se mantiene: los estilos viven en `.qss`, y el Python solo lee
  colores de `palette`.

## 4. Orden propuesto

1. **E1 + E3**: paleta única y fuente. Es la base de todo lo demás.
2. **E2**: iconos Lucide.
3. **E4 a + b**: toolbar y barra del visor, lo que el operador ve todo el día.
4. **E4 c + d**: launcher y barra de estado.
5. **E4 e + f**: panel derecho y lista de pasos.

Cada paso es un commit con su captura.
