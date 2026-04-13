<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const displayName = ref('')
const tenantName = ref('')

async function onSubmit() {
  try {
    await auth.register({
      email: email.value,
      password: password.value,
      display_name: displayName.value,
      tenant_name: tenantName.value,
    })
    router.push('/login')
  } catch {
    // error se muestra via auth.error
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-base px-4 py-8">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary-soft border border-primary/30 mb-3">
          <svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h1 class="text-xl font-bold text-text">DocScan Studio</h1>
        <p class="text-xs text-subtext mt-1">Captura y gestión documental</p>
      </div>

      <form
        @submit.prevent="onSubmit"
        class="bg-white rounded-lg shadow-sm border border-surface-0 p-6 space-y-4"
      >
        <h2 class="text-base font-semibold text-text">Crear cuenta</h2>

        <div v-if="auth.error" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2">
          {{ auth.error }}
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Nombre</label>
          <input
            v-model="displayName"
            type="text"
            required
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Organización</label>
          <input
            v-model="tenantName"
            type="text"
            required
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            placeholder="Nombre de la empresa"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Contraseña</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <button
          type="submit"
          :disabled="auth.loading"
          class="w-full bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover disabled:opacity-50 transition-colors"
        >
          {{ auth.loading ? 'Registrando...' : 'Registrarse' }}
        </button>

        <p class="text-xs text-center text-subtext">
          ¿Ya tienes cuenta?
          <router-link to="/login" class="text-primary hover:text-primary-hover font-medium">Iniciar sesión</router-link>
        </p>
      </form>
    </div>
  </div>
</template>
