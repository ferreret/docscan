<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError } from '@/api/client'

const route = useRoute()
const router = useRouter()

const token = route.params.token as string
const password = ref('')
const displayName = ref('')
const error = ref<string | null>(null)
const submitting = ref(false)
const success = ref(false)

async function onSubmit() {
  error.value = null
  submitting.value = true
  try {
    await api.post('/invitations/accept', {
      token,
      password: password.value,
      display_name: displayName.value,
    })
    success.value = true
    setTimeout(() => router.push('/login'), 1500)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al aceptar la invitación'
  } finally {
    submitting.value = false
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
        <p class="text-xs text-subtext mt-1">Completa tu registro</p>
      </div>

      <form
        v-if="!success"
        @submit.prevent="onSubmit"
        class="bg-base rounded-lg shadow-sm border border-surface-0 p-6 space-y-4"
      >
        <h2 class="text-base font-semibold text-text">Aceptar invitación</h2>

        <div v-if="error" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2">
          {{ error }}
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Nombre</label>
          <input
            v-model="displayName"
            type="text"
            required
            class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Contraseña</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="8"
            class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          <p class="text-[11px] text-subtext mt-1">Mínimo 8 caracteres.</p>
        </div>

        <button
          type="submit"
          :disabled="submitting"
          class="w-full bg-primary text-base rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover disabled:opacity-50 transition-colors"
        >
          {{ submitting ? 'Aceptando…' : 'Aceptar y crear cuenta' }}
        </button>
      </form>

      <div
        v-else
        class="bg-base rounded-lg shadow-sm border border-success/30 p-6 text-center space-y-2"
      >
        <p class="text-success font-semibold">¡Cuenta creada!</p>
        <p class="text-xs text-subtext">Redirigiendo al login…</p>
      </div>
    </div>
  </div>
</template>
