<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')

async function onSubmit() {
  try {
    await auth.login({ email: email.value, password: password.value })
    router.push('/')
  } catch {
    // error se muestra via auth.error
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-sm">
      <h1 class="text-2xl font-bold text-gray-900 text-center mb-8">DocScan Studio</h1>

      <form @submit.prevent="onSubmit" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-900">Iniciar sesión</h2>

        <div v-if="auth.error" class="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {{ auth.error }}
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="usuario@empresa.com"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <button
          type="submit"
          :disabled="auth.loading"
          class="w-full bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {{ auth.loading ? 'Entrando...' : 'Entrar' }}
        </button>

        <p class="text-sm text-center text-gray-500">
          ¿Sin cuenta?
          <router-link to="/register" class="text-blue-600 hover:text-blue-700 font-medium">Registrarse</router-link>
        </p>
      </form>
    </div>
  </div>
</template>
