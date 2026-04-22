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
