<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const store = useAdminStore()
const toast = useToast()

const tenantName = ref('')
const plan = ref('free')
const adminEmail = ref('')
const adminPassword = ref('')
const adminDisplayName = ref('')

const submitting = ref(false)
const error = ref<string | null>(null)

const passwordTooShort = computed(
  () => adminPassword.value.length > 0 && adminPassword.value.length < 8,
)

async function onSubmit() {
  error.value = null

  if (adminPassword.value.length < 8) {
    error.value = 'La contraseña del admin debe tener al menos 8 caracteres.'
    return
  }

  submitting.value = true
  try {
    const tenant = await store.createTenant({
      tenant_name: tenantName.value,
      plan: plan.value,
      admin_email: adminEmail.value,
      admin_password: adminPassword.value,
      admin_display_name: adminDisplayName.value,
    })
    toast.success(`Tenant "${tenant.name}" creado`)
    router.push(`/admin/tenants/${tenant.id}`)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error creando tenant'
  } finally {
    submitting.value = false
  }
}

function onCancel() {
  router.push('/admin/tenants')
}
</script>

<template>
  <div class="max-w-2xl">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text">Nuevo tenant</h1>
      <p class="text-xs text-subtext mt-1">
        Crea el tenant y su primer administrador. Recibirá acceso inmediato con
        las credenciales que indiques aquí.
      </p>
    </div>

    <form
      @submit.prevent="onSubmit"
      class="bg-base rounded-lg border border-surface-0 p-6 space-y-5"
    >
      <div
        v-if="error"
        class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2"
      >
        {{ error }}
      </div>

      <fieldset>
        <legend class="text-[11px] uppercase tracking-wide text-subtext font-semibold mb-3">
          Empresa
        </legend>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Nombre del tenant</label>
            <input
              v-model="tenantName"
              data-test="tenant-name"
              type="text"
              required
              maxlength="200"
              placeholder="Acme S.A."
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Plan</label>
            <select
              v-model="plan"
              data-test="plan-select"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary"
            >
              <option value="free">free</option>
              <option value="basic">basic</option>
              <option value="enterprise">enterprise</option>
            </select>
          </div>
        </div>
      </fieldset>

      <fieldset class="border-t border-surface-0 pt-5">
        <legend class="text-[11px] uppercase tracking-wide text-subtext font-semibold mb-3">
          Primer administrador
        </legend>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Email</label>
            <input
              v-model="adminEmail"
              data-test="admin-email"
              type="email"
              required
              placeholder="admin@empresa.com"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Nombre visible</label>
            <input
              v-model="adminDisplayName"
              data-test="admin-display-name"
              type="text"
              required
              maxlength="200"
              placeholder="Nombre Apellido"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">
              Contraseña inicial
              <span class="text-subtext font-normal">· mín. 8 caracteres</span>
            </label>
            <input
              v-model="adminPassword"
              data-test="admin-password"
              type="password"
              required
              minlength="8"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              :class="passwordTooShort ? 'border-danger' : ''"
            />
          </div>
        </div>
      </fieldset>

      <div class="flex justify-end gap-2 pt-2 border-t border-surface-0">
        <button
          type="button"
          data-test="cancel"
          @click="onCancel"
          class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors"
        >
          Cancelar
        </button>
        <button
          type="submit"
          :disabled="submitting"
          class="bg-primary text-base px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover disabled:opacity-50 transition-colors"
        >
          {{ submitting ? 'Creando…' : 'Crear tenant' }}
        </button>
      </div>
    </form>
  </div>
</template>
