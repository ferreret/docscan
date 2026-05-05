import { ref, computed, type Ref, type ComputedRef } from 'vue'

export type ThemePreference = 'auto' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'theme'
export const VALID_THEME_PREFERENCES: readonly ThemePreference[] = ['auto', 'light', 'dark']

/** Lee y sanea la preferencia almacenada. Compartido con main.ts (pre-mount). */
export function readStoredThemePreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    return VALID_THEME_PREFERENCES.includes(raw as ThemePreference)
      ? (raw as ThemePreference)
      : 'auto'
  } catch {
    return 'auto'
  }
}

/** Detecta si el SO prefiere oscuro. Compartido con main.ts (pre-mount). */
export function osPrefersDarkScheme(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

/** Resuelve preferencia a tema concreto consultando OS si es 'auto'. */
export function resolveTheme(pref: ThemePreference): ResolvedTheme {
  if (pref === 'light') return 'light'
  if (pref === 'dark') return 'dark'
  return osPrefersDarkScheme() ? 'dark' : 'light'
}

const preference = ref<ThemePreference>(readStoredThemePreference())
const osDark = ref<boolean>(osPrefersDarkScheme())

const current = computed<ResolvedTheme>(() => {
  if (preference.value === 'light') return 'light'
  if (preference.value === 'dark') return 'dark'
  return osDark.value ? 'dark' : 'light'
})

function setPreference(p: ThemePreference): void {
  preference.value = p
  try {
    localStorage.setItem(THEME_STORAGE_KEY, p)
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
  preference.value = readStoredThemePreference()
  osDark.value = osPrefersDarkScheme()
  osListenerAttached = false
}
