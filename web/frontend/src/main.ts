import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { readStoredThemePreference, resolveTheme } from './composables/useTheme'
import './style.css'

// Aplicar el tema ANTES del mount para evitar FOUC.
// El composable useTheme.ts lee este estado inicial cuando se invoca.
document.documentElement.dataset.theme = resolveTheme(readStoredThemePreference())

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
