# Sistema de tema global (Fase 1 del Workbench web)

**Fecha**: 2026-04-22
**Estado**: aprobado, pendiente plan de implementación
**Sub-proyecto**: 1 de 4 del Workbench web

## Contexto

El Workbench Qt (PySide6) permite alternar tema claro/oscuro y escalar la fuente. La web actual de DocScan Studio (rama `feature/web`) usa Catppuccin Latte (claro) hardcoded en `web/frontend/src/style.css`. No existe mecanismo para cambiar a tema oscuro ni preferencia persistida del usuario.

Esta spec define la **Fase 1** del sub-proyecto Workbench web, que se descompone en cuatro fases secuenciales:

1. **Sistema de tema global** (esta spec)
2. Workbench base (layout 3 paneles, visor, miniaturas, BarcodePanel view-only, MetadataPanel/Lote)
3. Workbench polish (overlays fields, rotación, Log, edición barcodes, edición páginas, drag-drop)
4. Shortcuts + 4 eventos lifecycle nuevos

La Fase 1 es **independiente del Workbench**: aporta valor a toda la web (configurador, listas, dashboard) y deja la base lista para que las Fases 2-4 la den por hecha.

## Objetivos

- Permitir al usuario elegir entre tema claro, oscuro y auto (según preferencia del SO).
- Persistir la preferencia entre sesiones (`localStorage`).
- Aplicar el tema a **toda la web** sin parpadeo (FOUC).
- Mantener cero deuda técnica: variables CSS semánticas duales, sin colores hardcoded en componentes.

## No objetivos

- Personalización de colores individuales (sliders, color pickers).
- Más de un tema oscuro / más de un tema claro.
- Aplicar el tema a recursos externos (PDFs embebidos, imágenes con fondo blanco fijo dentro del visor).
- Shortcut de teclado para alternar tema (puede añadirse en Fase 4 con el resto de shortcuts).

## Arquitectura

Sistema basado en `<html data-theme="light|dark">` con dos bloques de variables CSS y un composable Vue que sincroniza preferencia, detección del SO y persistencia.

### Flujo de datos

```
Usuario click ☀️ en <ThemeSelector>
  → useTheme.setPreference('light')
    → localStorage['theme'] = 'light'
    → preference.value = 'light'
    → current.value = 'light'  (resuelto)
    → document.documentElement.dataset.theme = 'light'
    → CSS recalcula colores via [data-theme="light"]
```

Para `preference === 'auto'`, `current` se calcula desde `matchMedia('(prefers-color-scheme: dark)')` y se actualiza en vivo si el SO cambia (listener `change`).

### Resolución inicial (sin FOUC)

El tema se aplica al `<html>` ANTES del mount de Vue, en el script de entrada (`main.ts`):

```ts
// main.ts (antes de createApp)
const stored = localStorage.getItem('theme')
const preference = ['auto', 'light', 'dark'].includes(stored ?? '') ? stored! : 'auto'
const resolved = preference === 'auto'
  ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  : preference
document.documentElement.dataset.theme = resolved
```

El composable `useTheme` lee este estado inicial y lo expone reactivo.

## Componentes

### `composables/useTheme.ts` (nuevo)

Singleton-style composable. Estado compartido entre todas las llamadas:

```ts
type ThemePreference = 'auto' | 'light' | 'dark'
type ResolvedTheme = 'light' | 'dark'

interface ThemeState {
  preference: Ref<ThemePreference>      // qué eligió el usuario
  current: ComputedRef<ResolvedTheme>   // qué se está pintando ahora mismo
  setPreference: (p: ThemePreference) => void
}

export function useTheme(): ThemeState
```

Responsabilidades:

- Leer preferencia inicial de `localStorage` con sanitización (valores inválidos → 'auto').
- Mantener `current` reactivo basado en `preference` y `matchMedia`.
- En `setPreference`: actualizar ref + persistir + aplicar `data-theme`.
- Listener `matchMedia` change cuando preference='auto' para detección OS en vivo.
- Cleanup del listener si nunca se usa (no necesario para singleton).

### `components/ThemeSelector.vue` (nuevo)

Grupo de tres botones segmented:

- ☀️ Claro · ☉ Auto · 🌙 Oscuro
- `aria-pressed="true"` en el activo
- `aria-label` descriptivo en cada uno
- Tooltip via `title` con el modo
- Visualmente: botones unidos con border-radius compartidos en extremos

Props: ninguna. Usa `useTheme()` directamente.

Tamaño compacto para encajar en el sidebar (no se ve bien con texto, solo iconos).

### `tests/composables/useTheme.test.ts` (nuevo)

Tests vitest:

1. Carga 'auto' por defecto si no hay nada en localStorage.
2. Carga la preferencia de localStorage si existe y es válida.
3. Sanea valores inválidos a 'auto'.
4. setPreference('dark') actualiza ref + localStorage + atributo `<html>`.
5. preference='auto' → current cambia cuando matchMedia cambia (con mock).
6. preference='light' → current siempre 'light' aunque matchMedia diga otro.
7. localStorage bloqueado (try/catch) → fallback a memoria sin error.

### `tests/components/ThemeSelector.test.ts` (nuevo)

Tests vitest:

1. Renderiza 3 botones (claro, auto, oscuro).
2. El botón correspondiente a `preference` actual tiene `aria-pressed="true"`.
3. Click en cada botón llama `setPreference` con el valor correcto.
4. Cambia el `aria-pressed` reactivamente al cambiar preference.

## Cambios en archivos existentes

### `web/frontend/src/style.css`

Añadir bloque `[data-theme="dark"]` con la paleta Mocha. Mantener el `@theme` actual como **default** (el tema claro es el fallback cuando no hay `data-theme` o vale `"light"`). El script de inicialización siempre escribe `data-theme="light"` o `"dark"`, nunca lo omite, para evitar ambigüedad.

```css
@theme {
  /* default = light = Latte (igual que ahora) */
  --color-base: #eff1f5;
  /* ... resto igual ... */
}

[data-theme="dark"] {
  --color-base: #1e1e2e;
  --color-mantle: #181825;
  --color-crust: #11111b;
  --color-surface-0: #313244;
  --color-surface-1: #45475a;
  --color-surface-2: #585b70;
  --color-overlay-0: #6c7086;
  --color-overlay-1: #7f849c;
  --color-subtext: #a6adc8;
  --color-text: #cdd6f4;

  --color-primary: #89b4fa;
  --color-primary-hover: #74c7ec;
  --color-primary-soft: #313244;

  --color-danger: #f38ba8;
  --color-danger-soft: #45475a;
  --color-success: #a6e3a1;
  --color-success-soft: #45475a;
  --color-warning: #fab387;
  --color-warning-soft: #45475a;
}
```

Verificar que Tailwind v4 reconoce variables CSS dentro de `[data-theme="dark"]` para que las clases utility (`bg-base`, `text-text`, etc.) cambien dinámicamente. Si Tailwind v4 requiere que las variables estén dentro de `@theme`, usar la directiva `@variant dark` con `@theme` dual.

### `web/frontend/src/main.ts`

Añadir el bloque de aplicación inicial del tema antes de `createApp(App).mount(...)`. Ver "Resolución inicial" arriba.

### `web/frontend/src/layouts/AppLayout.vue`

Insertar `<ThemeSelector />` en el card de usuario, encima del botón "Cerrar sesión":

```vue
<div class="user-card">
  <p>{{ user.name }}</p>
  <p>{{ user.email }}</p>
  <ThemeSelector />     <!-- nuevo -->
  <button>Cerrar sesión</button>
</div>
```

### `web/frontend/index.html`

Añadir al `<head>` o al CSS:

```css
html { color-scheme: light dark; }
```

Esto hace que los scrollbars nativos del SO (en Firefox/Safari) sigan el tema sin custom CSS.

## Auditoría de colores hardcoded

Antes de declarar Fase 1 completa, auditar todos los componentes Vue (`web/frontend/src/**/*.vue`) en busca de:

- Clases Tailwind con colores literales: `bg-white`, `bg-gray-*`, `text-gray-*`, `text-black`, `border-gray-*`, etc.
- Colores hex inline en `style=""`.
- Imports de paletas externas.

Cada hallazgo se reemplaza por la variable semántica equivalente (`bg-base`, `text-text`, etc.). Si una variable no existe, se documenta y se decide caso por caso.

Componentes con tratamiento especial conocido:

- **DocumentViewer**: el fondo del visor probablemente debe ser oscuro siempre (las imágenes destacan mejor). Si está hardcoded a blanco, mantenerlo o usar `--color-mantle` que es oscuro en oscuro y claro en claro.
- **Logos** (sidebar header): si dependen de fondo, generar variantes o usar SVG con `currentColor`.

Esta auditoría puede añadir 0-4h al trabajo según cuántas excepciones aparezcan. Se contabiliza como parte del scope de Fase 1.

## Manejo de errores

- `localStorage` no disponible (modo privado, bloqueo): try/catch silencioso. La preferencia vive solo en memoria durante la sesión.
- `matchMedia` no disponible (navegador muy viejo): fallback a `light`.
- Valor en localStorage no es 'auto'/'light'/'dark': sanear a 'auto'.

Sin toasts ni avisos visuales; los errores son benignos.

## Testing

- **Composable y selector**: tests vitest descritos arriba (~11 tests entre los dos).
- **Suite existente**: ningún test debe romperse. Si alguno asume colores claros explícitos, ajustarlo.
- **QA visual con Playwright**: tras implementar, recorrer 3 modos (claro/oscuro/auto con SO en oscuro) en al menos: login, dashboard, applications list, una pestaña del configurador (la más compleja: PipelineEditorView), una vista de batch detail. Confirmar que no hay colores rotos.

## Restricciones / decisiones tomadas

- **Paleta oscura = Catppuccin Mocha** (complemento natural de Latte). No se evalúan otras.
- **Mecanismo = `data-theme` attribute** (no class, no media query directa). Permite override y testing fácil.
- **Persistencia = `localStorage` clave 'theme'** con valores 'auto'/'light'/'dark'.
- **Toggle UI en sidebar** (card de usuario, encima de "Cerrar sesión"). 3 botones segmented.
- **Sin shortcut de teclado** en esta fase (queda para Fase 4 si se quiere).
- **Sin opción de personalizar colores individuales** (YAGNI).

## Out of scope

- Migración de las decisiones de fuente del desktop (escalar tipografía con +/-): no contemplado.
- Respeto a `prefers-reduced-motion`: ya lo cubre Tailwind por defecto en transiciones.
- Tema "alto contraste" para accesibilidad: futuro.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Tailwind v4 + variables CSS en `[data-theme]` | Verificar en proof-of-concept antes de redactar el plan. Si no funciona, usar `:root` con clases (`html.dark`) y reescribir variables en el bloque `.dark` |
| Auditoría descubre muchos colores hardcoded | Documentar cada uno, cambiar caso por caso. Si excede 4h, escalar al usuario. |
| FOUC al cargar | Aplicar `data-theme` en `main.ts` ANTES del mount. Si persiste, mover el script al `<head>` de `index.html` (script inline blocking). |
| El `<DocumentViewer>` con imágenes blancas se ve raro en oscuro | Decidir caso por caso: padding, fondo gris medio, o forzar fondo oscuro siempre. |

## Plan de commits sugerido

1. Variables CSS duales en `style.css` + script inicial en `main.ts`
2. Composable `useTheme` + tests
3. Componente `<ThemeSelector>` + tests
4. Integración en `AppLayout.vue`
5. Auditoría de colores hardcoded (1 commit por ámbito si hay muchos cambios)

## Verificación de cierre

- Suite vitest: 100% passing (incluyendo nuevos tests).
- Typecheck OK.
- QA visual Playwright en 3 modos sobre vistas representativas.
- Push a `origin/feature/web`.
