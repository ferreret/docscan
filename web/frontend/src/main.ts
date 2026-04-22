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
