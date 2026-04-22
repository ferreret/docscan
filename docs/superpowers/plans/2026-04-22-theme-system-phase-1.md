# Sistema de tema global (Fase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir tema claro/oscuro/auto con persistencia y detección OS al frontend Vue 3 de DocScan Studio, aplicado globalmente a toda la web.

**Architecture:** `<html data-theme="light|dark">` con CSS variables duales (Catppuccin Latte + Mocha). Composable singleton `useTheme` sincroniza preferencia (localStorage), detección `matchMedia` y atributo DOM. Componente `<ThemeSelector>` (tres botones segmented) integrado en el sidebar.

**Tech Stack:** Vue 3 (Composition API, `<script setup>`), TypeScript estricto, Tailwind v4 con `@theme`, Vitest + @vue/test-utils, Pinia (no necesario aquí).

**Spec:** `docs/superpowers/specs/2026-04-22-theme-system-phase-1-design.md`

---

## File Structure

**Create:**
- `web/frontend/src/composables/useTheme.ts` — composable singleton con preference/current/setPreference
- `web/frontend/src/components/ThemeSelector.vue` — UI tres botones segmented (☀️ ☉ 🌙)
- `web/frontend/tests/composables/useTheme.test.ts` — 7 tests vitest
- `web/frontend/tests/components/ThemeSelector.test.ts` — 4 tests vitest

**Modify:**
- `web/frontend/src/style.css` — añadir bloque `[data-theme="dark"]` con paleta Mocha
- `web/frontend/src/main.ts` — bloque inicial pre-mount que aplica `data-theme`
- `web/frontend/index.html` — añadir `color-scheme: light dark` al CSS inline
- `web/frontend/src/layouts/AppLayout.vue` — insertar `<ThemeSelector>` en card de usuario
- `web/frontend/tests/setup.ts` (opcional) — mock matchMedia si no existe

---

## Task 1: Variables CSS duales + paleta Mocha

**Files:**
- Modify: `web/frontend/src/style.css`

- [ ] **Step 1: Editar style.css con paleta Mocha bajo `[data-theme="dark"]`**

Reemplazar el contenido completo del archivo por:

```css
@import "tailwindcss";

@theme {
  /* Default = Catppuccin Latte (claro). Sobrescrito por [data-theme="dark"]. */
  --color-base: #eff1f5;
  --color-mantle: #e6e9ef;
  --color-crust: #dce0e8;
  --color-surface-0: #ccd0da;
  --color-surface-1: #bcc0cc;
  --color-surface-2: #acb0be;
  --color-overlay-0: #9ca0b0;
  --color-overlay-1: #8c8fa1;
  --color-subtext: #6c6f85;
  --color-text: #4c4f69;

  --color-primary: #1e66f5;
  --color-primary-hover: #4080f7;
  --color-primary-soft: #e8ecf5;

  --color-danger: #d20f39;
  --color-danger-soft: #fce4e4;
  --color-success: #40a02b;
  --color-success-soft: #e2f1db;
  --color-warning: #df8e1d;
  --color-warning-soft: #faeccd;

  --font-sans: "Segoe UI", "Inter", "Ubuntu", system-ui, sans-serif;

  --radius-card: 0.5rem;
}

/* Tema oscuro = Catppuccin Mocha. Sobrescribe las mismas variables CSS;
   las utilities de Tailwind las leen dinámicamente desde var(--color-*). */
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

html,
body {
  background-color: var(--color-base);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 13px;
}

html {
  color-scheme: light dark;
}

/* Scrollbar estilo desktop */
*::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
*::-webkit-scrollbar-track {
  background: var(--color-base);
}
*::-webkit-scrollbar-thumb {
  background: var(--color-surface-1);
  border-radius: 5px;
}
*::-webkit-scrollbar-thumb:hover {
  background: var(--color-surface-2);
}
```

- [ ] **Step 2: Ejecutar suite vitest para verificar regresión cero**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -10`
Expected: `Tests 152 passed (152)` (mismo número que antes; ningún test del frontend lee `style.css`).

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/style.css
git commit -m "feat(web-frontend): añadir paleta oscura Catppuccin Mocha en style.css

Las variables CSS bajo [data-theme=dark] sobrescriben las de @theme
(Latte). Las utilities de Tailwind las leen via var(--color-*) y
cambian dinámicamente al alternar el atributo data-theme en <html>.
También añade color-scheme: light dark para que los scrollbars
nativos sigan al tema."
```

---

## Task 2: Composable `useTheme`

**Files:**
- Create: `web/frontend/src/composables/useTheme.ts`
- Create: `web/frontend/tests/composables/useTheme.test.ts`

- [ ] **Step 1: Escribir el primer test failing — defaults a 'auto'**

Crear `web/frontend/tests/composables/useTheme.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTheme, _resetThemeForTests } from '@/composables/useTheme'

function setMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    setMatchMedia(false)
    _resetThemeForTests()
  })

  it('defaults to "auto" when localStorage is empty', () => {
    const { preference } = useTheme()
    expect(preference.value).toBe('auto')
  })
})
```

- [ ] **Step 2: Ejecutar test, verificar que falla por módulo no existente**

Run: `cd web/frontend && npx vitest run tests/composables/useTheme.test.ts 2>&1 | tail -5`
Expected: FAIL con mensaje del tipo `Failed to resolve import "@/composables/useTheme"` o `Cannot find module`.

- [ ] **Step 3: Crear composable mínimo para que pase el primer test**

Crear `web/frontend/src/composables/useTheme.ts`:

```ts
import { ref, computed, type Ref, type ComputedRef } from 'vue'

export type ThemePreference = 'auto' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'theme'
const VALID: ThemePreference[] = ['auto', 'light', 'dark']

function readStoredPreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return VALID.includes(raw as ThemePreference) ? (raw as ThemePreference) : 'auto'
  } catch {
    return 'auto'
  }
}

function osPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

const preference = ref<ThemePreference>(readStoredPreference())
const osDark = ref<boolean>(osPrefersDark())

const current = computed<ResolvedTheme>(() => {
  if (preference.value === 'light') return 'light'
  if (preference.value === 'dark') return 'dark'
  return osDark.value ? 'dark' : 'light'
})

function setPreference(p: ThemePreference): void {
  preference.value = p
  try {
    localStorage.setItem(STORAGE_KEY, p)
  } catch {
    /* localStorage bloqueado: solo memoria */
  }
  document.documentElement.dataset.theme = current.value
}

let osListenerAttached = false
function attachOsListener(): void {
  if (osListenerAttached) return
  try {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', (e) => {
      osDark.value = e.matches
      if (preference.value === 'auto') {
        document.documentElement.dataset.theme = current.value
      }
    })
    osListenerAttached = true
  } catch {
    /* matchMedia no disponible */
  }
}

interface ThemeApi {
  preference: Ref<ThemePreference>
  current: ComputedRef<ResolvedTheme>
  setPreference: (p: ThemePreference) => void
}

export function useTheme(): ThemeApi {
  attachOsListener()
  return { preference, current, setPreference }
}

/** Solo para tests: resetea el estado singleton entre tests. */
export function _resetThemeForTests(): void {
  preference.value = readStoredPreference()
  osDark.value = osPrefersDark()
  osListenerAttached = false
}
```

- [ ] **Step 4: Ejecutar test, verificar que pasa**

Run: `cd web/frontend && npx vitest run tests/composables/useTheme.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes al mismo fichero**

Añadir dentro del `describe('useTheme', ...)`, después del primer `it`:

```ts
  it('loads valid preference from localStorage', () => {
    localStorage.setItem('theme', 'dark')
    _resetThemeForTests()
    const { preference } = useTheme()
    expect(preference.value).toBe('dark')
  })

  it('sanitizes invalid localStorage value to "auto"', () => {
    localStorage.setItem('theme', 'pink')
    _resetThemeForTests()
    const { preference } = useTheme()
    expect(preference.value).toBe('auto')
  })

  it('setPreference updates ref, localStorage and html data-theme', () => {
    const { setPreference, preference } = useTheme()
    setPreference('dark')
    expect(preference.value).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('current reflects OS when preference is "auto"', () => {
    setMatchMedia(true) // OS prefers dark
    _resetThemeForTests()
    const { current } = useTheme()
    expect(current.value).toBe('dark')
  })

  it('current ignores OS when preference is forced', () => {
    setMatchMedia(true) // OS prefers dark
    _resetThemeForTests()
    const { setPreference, current } = useTheme()
    setPreference('light')
    expect(current.value).toBe('light')
  })

  it('falls back gracefully when localStorage throws', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    const { setPreference, preference } = useTheme()
    expect(() => setPreference('dark')).not.toThrow()
    expect(preference.value).toBe('dark')
    setItemSpy.mockRestore()
  })

  it('falls back to light when matchMedia throws', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: () => {
        throw new Error('not supported')
      },
    })
    _resetThemeForTests()
    const { current } = useTheme()
    expect(current.value).toBe('light')
  })
```

- [ ] **Step 6: Ejecutar todos los tests del composable, verificar que todos pasan**

Run: `cd web/frontend && npx vitest run tests/composables/useTheme.test.ts 2>&1 | tail -8`
Expected: `Tests 8 passed (8)` (1 original + 7 nuevos).

- [ ] **Step 7: Ejecutar suite completa para verificar regresión cero**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 160 passed (160)` (152 previos + 8 nuevos).

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/composables/useTheme.ts web/frontend/tests/composables/useTheme.test.ts
git commit -m "feat(web-frontend): composable useTheme con auto/light/dark

Singleton-style composable que sincroniza la preferencia del usuario
(localStorage 'theme' con valores auto/light/dark), la preferencia del
SO via matchMedia, y el atributo <html data-theme=...>. Listener al
SO en vivo cuando preference='auto'. Fallbacks silenciosos si
localStorage o matchMedia fallan.

8 tests vitest cubren defaults, persistencia, saneo de valores
inválidos, override sobre el SO, y todos los fallbacks de error."
```

---

## Task 3: Componente `<ThemeSelector>`

**Files:**
- Create: `web/frontend/src/components/ThemeSelector.vue`
- Create: `web/frontend/tests/components/ThemeSelector.test.ts`

- [ ] **Step 1: Escribir el primer test failing — renderiza 3 botones**

Crear `web/frontend/tests/components/ThemeSelector.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ThemeSelector from '@/components/ThemeSelector.vue'
import { _resetThemeForTests } from '@/composables/useTheme'

describe('ThemeSelector', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    _resetThemeForTests()
  })

  it('renders three buttons (light, auto, dark)', () => {
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[0].attributes('aria-label')).toContain('claro')
    expect(buttons[1].attributes('aria-label')).toContain('autom')
    expect(buttons[2].attributes('aria-label')).toContain('oscuro')
  })
})
```

- [ ] **Step 2: Ejecutar test, verificar que falla por componente no existente**

Run: `cd web/frontend && npx vitest run tests/components/ThemeSelector.test.ts 2>&1 | tail -5`
Expected: FAIL con `Failed to resolve import "@/components/ThemeSelector.vue"`.

- [ ] **Step 3: Crear componente mínimo**

Crear `web/frontend/src/components/ThemeSelector.vue`:

```vue
<script setup lang="ts">
import { useTheme, type ThemePreference } from '@/composables/useTheme'

const { preference, setPreference } = useTheme()

interface Option {
  value: ThemePreference
  label: string
  icon: string
}

const options: Option[] = [
  { value: 'light', label: 'Tema claro', icon: '☀' },
  { value: 'auto', label: 'Tema automático según el sistema', icon: '◐' },
  { value: 'dark', label: 'Tema oscuro', icon: '☾' },
]

function select(value: ThemePreference): void {
  setPreference(value)
}
</script>

<template>
  <div
    role="radiogroup"
    aria-label="Selector de tema"
    class="inline-flex rounded-md border border-surface-1 overflow-hidden"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="preference === opt.value"
      :aria-label="opt.label"
      :title="opt.label"
      class="px-2 py-1 text-xs leading-none transition-colors"
      :class="preference === opt.value
        ? 'bg-primary text-base font-semibold'
        : 'bg-mantle text-subtext hover:bg-crust hover:text-text'"
      @click="select(opt.value)"
    >
      {{ opt.icon }}
    </button>
  </div>
</template>
```

- [ ] **Step 4: Ejecutar test, verificar que pasa**

Run: `cd web/frontend && npx vitest run tests/components/ThemeSelector.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes**

Añadir dentro del `describe('ThemeSelector', ...)`, después del primer `it`:

```ts
  it('marks aria-checked on the active preference', () => {
    localStorage.setItem('theme', 'dark')
    _resetThemeForTests()
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons[0].attributes('aria-checked')).toBe('false')
    expect(buttons[1].attributes('aria-checked')).toBe('false')
    expect(buttons[2].attributes('aria-checked')).toBe('true')
  })

  it('clicking a button calls setPreference with the right value', async () => {
    const wrapper = mount(ThemeSelector)
    await wrapper.findAll('button')[2].trigger('click')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('updates aria-checked reactively after click', async () => {
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons[1].attributes('aria-checked')).toBe('true') // auto default
    await buttons[0].trigger('click')
    expect(buttons[0].attributes('aria-checked')).toBe('true')
    expect(buttons[1].attributes('aria-checked')).toBe('false')
  })
```

- [ ] **Step 6: Ejecutar tests del selector**

Run: `cd web/frontend && npx vitest run tests/components/ThemeSelector.test.ts 2>&1 | tail -5`
Expected: `Tests 4 passed (4)` (1 original + 3 nuevos).

- [ ] **Step 7: Ejecutar suite completa**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 164 passed (164)` (160 previos + 4 nuevos).

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/components/ThemeSelector.vue web/frontend/tests/components/ThemeSelector.test.ts
git commit -m "feat(web-frontend): componente ThemeSelector segmented (3 botones)

Grupo segmented con tres botones (☀ ◐ ☾) que conectan con el
composable useTheme. Patrón role=radiogroup + aria-checked para
accesibilidad. Tooltip y aria-label en español.

4 tests vitest cubren render, marca del activo según preference,
click sincroniza con localStorage + DOM, y reactividad."
```

---

## Task 4: Aplicación inicial pre-mount + color-scheme

**Files:**
- Modify: `web/frontend/src/main.ts`

- [ ] **Step 1: Editar main.ts añadiendo el bloque pre-mount**

Reemplazar el contenido completo de `web/frontend/src/main.ts` por:

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

// Aplicar el tema ANTES del mount para evitar FOUC.
// El composable useTheme.ts lee este estado inicial cuando se invoca.
;(() => {
  const VALID = ['auto', 'light', 'dark'] as const
  type Pref = (typeof VALID)[number]
  let pref: Pref = 'auto'
  try {
    const raw = localStorage.getItem('theme')
    if (VALID.includes(raw as Pref)) pref = raw as Pref
  } catch {
    /* localStorage bloqueado */
  }
  let resolved: 'light' | 'dark' = 'light'
  if (pref === 'dark') resolved = 'dark'
  else if (pref === 'light') resolved = 'light'
  else {
    try {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    } catch {
      resolved = 'light'
    }
  }
  document.documentElement.dataset.theme = resolved
})()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 2: Ejecutar suite + typecheck**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -5 && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: `Tests 164 passed (164)` y typecheck sin errores.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/main.ts
git commit -m "feat(web-frontend): aplicar data-theme antes del mount Vue

Resuelve la preferencia (localStorage o matchMedia OS) y escribe
data-theme en <html> ANTES de createApp().mount(). Evita el FOUC
(parpadeo claro→oscuro) al cargar la página. El composable useTheme
lee ese estado inicial al primer uso y lo expone reactivo."
```

---

## Task 5: Integrar `<ThemeSelector>` en el sidebar

**Files:**
- Modify: `web/frontend/src/layouts/AppLayout.vue`

- [ ] **Step 1: Inspeccionar el card de usuario en AppLayout**

Read: `web/frontend/src/layouts/AppLayout.vue` líneas 50-90.

El card de usuario actual está estructurado:

```vue
<div class="p-3 border-t border-surface-0">
  <div class="flex items-center gap-2.5 px-2 py-1.5">
    <div class="w-8 h-8 rounded-full ...">{{ initial }}</div>
    <div class="flex-1 min-w-0">
      <p>{{ display_name }}</p>
      <p>{{ email }}</p>
    </div>
    <button @click="auth.logout()">...</button>
  </div>
</div>
```

- [ ] **Step 2: Modificar AppLayout para insertar ThemeSelector encima del card**

En `web/frontend/src/layouts/AppLayout.vue`:

a) Añadir al import en `<script setup>` (línea 2):

```ts
import { useAuthStore } from '@/stores/auth'
import ThemeSelector from '@/components/ThemeSelector.vue'

const auth = useAuthStore()
```

b) En el bloque del card de usuario (cerca de línea 60), reemplazar:

```vue
      <div class="p-3 border-t border-surface-0">
        <div class="flex items-center gap-2.5 px-2 py-1.5">
```

por:

```vue
      <div class="p-3 border-t border-surface-0 space-y-2">
        <div class="flex justify-center">
          <ThemeSelector />
        </div>
        <div class="flex items-center gap-2.5 px-2 py-1.5">
```

(añade un wrapper centrado con el selector encima del bloque existente, separados por `space-y-2`).

- [ ] **Step 3: Ejecutar suite + typecheck**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -5 && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: `Tests 164 passed (164)` y typecheck OK.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/layouts/AppLayout.vue
git commit -m "feat(web-frontend): integrar ThemeSelector en el sidebar

El selector de 3 botones aparece en el card de usuario, encima del
bloque con avatar/nombre/logout. Centrado y separado con space-y-2.
Visible siempre que el usuario esté autenticado."
```

---

## Task 6: Auditoría de colores hardcoded

**Files:**
- Modify: variable según hallazgos

Esta tarea identifica y arregla colores hardcoded que romperían el modo oscuro.

- [ ] **Step 1: Buscar colores Tailwind hardcoded**

Run:

```bash
cd web/frontend && grep -rEn '\b(bg|text|border|fill|stroke)-(white|black|gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-[0-9]+\b' src --include='*.vue' --include='*.ts' 2>&1 | grep -vE '__tests__|\.test\.' | head -50
```

Anotar todos los hallazgos en una lista. Si la lista está vacía, saltar a Step 5.

- [ ] **Step 2: Buscar hex inline en `style=""` y CSS embebido**

Run:

```bash
cd web/frontend && grep -rEn 'style="[^"]*#[0-9a-fA-F]{3,6}' src --include='*.vue' 2>&1 | head -30
cd web/frontend && grep -rEn 'background:\s*#|background-color:\s*#|color:\s*#' src --include='*.vue' --include='*.css' 2>&1 | grep -v '@theme\|\[data-theme' | head -30
```

Anotar hallazgos.

- [ ] **Step 3: Reemplazar cada hallazgo por la variable semántica equivalente**

Mapeo recomendado:

| Hardcoded | Reemplazo |
|---|---|
| `bg-white`, `bg-gray-50` | `bg-base` |
| `bg-gray-100`, `bg-gray-200` | `bg-mantle` o `bg-crust` |
| `bg-gray-800`, `bg-gray-900` | (en oscuro: ya cubierto por `bg-base`) |
| `text-black`, `text-gray-900` | `text-text` |
| `text-gray-500`, `text-gray-600` | `text-subtext` |
| `text-gray-400` | `text-overlay-0` |
| `border-gray-200`, `border-gray-300` | `border-surface-0` |
| `border-gray-400` | `border-surface-1` |
| `bg-blue-*` | `bg-primary` o `bg-primary-soft` |
| `bg-red-*` | `bg-danger` o `bg-danger-soft` |
| `bg-green-*` | `bg-success` o `bg-success-soft` |
| `bg-yellow-*`, `bg-orange-*` | `bg-warning` o `bg-warning-soft` |
| Hex inline | Variable equivalente o, si es decorativo (chart, etc.), dejar y documentar |

Para casos especiales:
- **Visor de imágenes**: si tiene `bg-white` y se vería mal en oscuro, reemplazar por `bg-mantle` (que es claro en claro y oscuro en oscuro).
- **SVG con `fill="black"` o `stroke="black"`**: cambiar a `fill="currentColor"` y dejar que el `text-text` o `text-subtext` del padre dicte el color.
- **Imágenes/logos PNG con fondo blanco**: añadir un fondo `bg-base` al wrapper (no se puede invertir el PNG, pero al menos se mezcla).

Reemplazar archivo por archivo, agrupando los cambios temáticamente para los commits.

- [ ] **Step 4: Tras cada lote de cambios, ejecutar suite + typecheck**

Run: `cd web/frontend && npx vitest run 2>&1 | tail -5 && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: tests siguen passing, typecheck OK.

- [ ] **Step 5: Commit (uno o varios según volumen)**

Si los cambios son pocos (<5 archivos), un solo commit:

```bash
git add web/frontend/src/...
git commit -m "fix(web-frontend): reemplazar colores hardcoded por variables semánticas

Necesario para el modo oscuro: bg-white → bg-base, text-gray-* →
text-text/subtext, border-gray-* → border-surface-*. Las utilities
de Tailwind ahora siguen el atributo data-theme via las CSS vars."
```

Si son muchos, agrupar por ámbito (auth/, batches/, applications/, etc.) con un commit por grupo.

- [ ] **Step 6: Si no hubo hallazgos, dejar constancia en el commit final del sub-proyecto**

(no commit aquí, solo nota mental para el QA visual).

---

## Task 7: QA visual con Playwright + push final

**Files:** ninguno modificado en esta tarea (solo verificación).

- [ ] **Step 1: Arrancar servicios locales**

Run en orden:

```bash
docker start docscan-pg
source /media/nicolas/DATA/Tecnomedia/FlexiPy/.venv/bin/activate
uvicorn web.api.main:create_app --factory --port 8001 > /tmp/uvicorn-qa-theme.log 2>&1 &
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run dev -- --port 5180 > /tmp/vite-qa-theme.log 2>&1 &
sleep 6
curl -s -o /dev/null -w "API:%{http_code}\nFrontend:" http://localhost:8001/docs
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5180
```

Expected: ambos `200`.

- [ ] **Step 2: Login y captura claro**

Con Playwright MCP:

```
mcp__playwright__browser_navigate http://localhost:5180/login
```

Login con `demo2@demo.com` / `demo12345`.

Tomar screenshot de:
- `/applications/8` (Resumen)
- `/applications/8/general` (formulario)
- `/applications/8/pipeline` (editor pipeline)
- `/batches/4` (BatchDetailView con miniaturas/visor)

Estado esperado: aplicación en tema claro Latte (default 'auto' si SO está en claro). Selector de tema visible en sidebar.

- [ ] **Step 3: Cambiar a tema oscuro y recapturar**

En la sesión Playwright, pulsar el botón ☾ del sidebar (o ejecutar `localStorage.setItem('theme', 'dark')` + reload).

Recorrer las mismas 4 vistas. Verificar:
- Fondo oscuro general
- Texto legible (contraste suficiente)
- Sidebar oscuro
- Tabs activos visibles
- Formularios con inputs distinguibles
- Badges (Activa, estados) visibles
- Sin colores hardcoded rotos (ej: cuadros blancos en mitad de un fondo oscuro)

Si encuentras algún color roto, anotarlo y volver a Task 6 para arreglarlo. Después re-correr este Step 3.

- [ ] **Step 4: Verificar persistencia y recarga sin FOUC**

Con tema oscuro activo:
1. Reload de la página (Ctrl+R via `mcp__playwright__browser_evaluate(() => location.reload())`).
2. Observar que la página carga directamente en oscuro, sin parpadeo claro.

- [ ] **Step 5: Verificar modo 'auto' siguiendo al SO**

Pulsar ◐ (auto). Cambiar el `prefers-color-scheme` desde Playwright:

```js
mcp__playwright__browser_evaluate(`() => {
  // emular prefers-color-scheme dark
  Object.defineProperty(window, 'matchMedia', {
    value: () => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }),
  });
  // disparar el listener manualmente vía recarga
  location.reload();
}`)
```

Verificar que en modo 'auto' con OS oscuro, la app se ve oscura.

(Esta verificación es light; el listener en vivo en navegador real sí se prueba mejor en QA manual.)

- [ ] **Step 6: Cerrar Playwright y matar servicios**

```
mcp__playwright__browser_close
pkill -f "uvicorn web.api"
pkill -f "vite.*--port 5180"
```

- [ ] **Step 7: Suite completa final + typecheck**

Run:

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: `Tests 164 passed (164)`, typecheck OK.

- [ ] **Step 8: Push a origin/feature/web**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git push origin feature/web 2>&1 | tail -5
```

Expected: push OK, commits visibles en remote.

---

## Self-Review

**Spec coverage** — repaso sección por sección del spec:

- ✅ Composable useTheme con preference/current/setPreference → Task 2
- ✅ Componente ThemeSelector segmented → Task 3
- ✅ Variables CSS duales (Latte + Mocha) → Task 1
- ✅ Aplicación pre-mount sin FOUC → Task 4
- ✅ Integración en sidebar → Task 5
- ✅ Auditoría de hardcoded colors → Task 6
- ✅ color-scheme: light dark en index.html → integrado en Task 1 (via style.css con html { color-scheme })
- ✅ Tests del composable (7) → Task 2 step 5
- ✅ Tests del selector (4) → Task 3 step 5
- ✅ Manejo de errores localStorage/matchMedia → Task 2 (fallbacks silenciosos en código + tests específicos)
- ✅ QA visual Playwright en vistas representativas → Task 7
- ✅ 3 modos verificados visualmente → Task 7 step 2-5

**Placeholder scan**: ningún TBD/TODO/vague hallado tras revisión.

**Type consistency**:
- `ThemePreference` y `ResolvedTheme` definidos en Task 2, importados en Task 3 ✅
- `_resetThemeForTests` definido en Task 2, usado en Tasks 2 y 3 ✅
- `setPreference`, `preference`, `current` exportados en Task 2, usados en Task 3 ✅

Plan completo.

---

## Execution Handoff

Plan completo y guardado en `docs/superpowers/plans/2026-04-22-theme-system-phase-1.md`.

Dos opciones de ejecución:

1. **Subagent-Driven (recomendada)** — dispatch un subagent fresco por task con review entre tasks. Iteración rápida.
2. **Inline Execution** — ejecutar tasks en esta sesión usando executing-plans, batch con checkpoints para review.
