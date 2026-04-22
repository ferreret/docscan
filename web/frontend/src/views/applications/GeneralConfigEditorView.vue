<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import AppHeader from '@/components/AppHeader.vue'

const SCANNER_BACKENDS = [
  { value: '', label: 'Sin escáner' },
  { value: 'sane', label: 'SANE (Linux)' },
  { value: 'twain', label: 'TWAIN (Windows)' },
  { value: 'wia', label: 'WIA (Windows)' },
] as const

interface GeneralConfig {
  name: string
  description: string
  active: boolean
  scanner_backend: string
  auto_transfer: boolean
  close_after_transfer: boolean
  background_color: string
}

const route = useRoute()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

const original = ref<GeneralConfig>({
  name: '',
  description: '',
  active: true,
  scanner_backend: '',
  auto_transfer: false,
  close_after_transfer: false,
  background_color: '',
})

const current = ref<GeneralConfig>({
  name: '',
  description: '',
  active: true,
  scanner_backend: '',
  auto_transfer: false,
  close_after_transfer: false,
  background_color: '',
})

const saving = ref(false)
const saveError = ref<string | null>(null)

const nameError = computed(() =>
  current.value.name.trim() === '' ? 'El nombre es obligatorio.' : null,
)

const hasChanges = computed(() => {
  const keys = Object.keys(original.value) as (keyof GeneralConfig)[]
  return keys.some((k) => original.value[k] !== current.value[k])
})

function configFromApp(): GeneralConfig {
  const app = appStore.current!
  return {
    name: app.name ?? '',
    description: app.description ?? '',
    active: app.active ?? true,
    scanner_backend: app.scanner_backend ?? '',
    auto_transfer: app.auto_transfer ?? false,
    close_after_transfer: app.close_after_transfer ?? false,
    background_color: app.background_color ?? '',
  }
}

async function loadFromStore(id: number): Promise<void> {
  await appStore.fetchOne(id)
  if (!appStore.current) return
  const cfg = configFromApp()
  original.value = { ...cfg }
  current.value = { ...cfg }
}

async function save(): Promise<void> {
  if (nameError.value) return
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, { ...current.value })
    original.value = { ...current.value }
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

function onBeforeUnload(ev: BeforeUnloadEvent): void {
  if (hasChanges.value) {
    ev.preventDefault()
    ev.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

watch(
  appId,
  async (id) => {
    if (typeof id === 'number' && !Number.isNaN(id)) {
      await loadFromStore(id)
    }
  },
  { immediate: true },
)

onBeforeRouteLeave((_to, _from, next) => {
  if (!hasChanges.value) return next()
  if (confirm('Hay cambios sin guardar. ¿Salir igualmente?')) return next()
  next(false)
})
</script>

<template>
  <div v-if="appStore.current">
    <AppHeader
      :app-id="appId"
      :app-name="appStore.current.name"
      :description="appStore.current.description || undefined"
    >
      <template #actions>
        <span v-if="hasChanges" class="text-xs text-warning">● sin guardar</span>
        <button
          type="button"
          data-test="save-general"
          :disabled="!hasChanges || !!nameError || saving"
          @click="save"
          class="text-[13px] bg-primary text-white rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <div v-if="saveError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-danger">
      {{ saveError }}
    </div>

    <div class="bg-white rounded-md border border-surface-0 p-6 max-w-2xl space-y-6">

      <!-- Nombre -->
      <div>
        <label for="field-name" class="block text-sm font-medium text-text mb-1">
          Nombre <span class="text-danger" aria-hidden="true">*</span>
        </label>
        <input
          id="field-name"
          v-model="current.name"
          type="text"
          data-test="field-name"
          placeholder="Nombre de la aplicación"
          class="w-full rounded border border-surface-0 px-3 py-2 text-sm text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary"
          :class="{ 'border-danger focus:ring-danger': nameError }"
          aria-required="true"
          :aria-invalid="nameError ? 'true' : undefined"
          :aria-describedby="nameError ? 'name-error' : undefined"
        />
        <p
          v-if="nameError"
          id="name-error"
          data-test="name-error"
          class="mt-1 text-xs text-danger"
          role="alert"
        >
          {{ nameError }}
        </p>
      </div>

      <!-- Descripción -->
      <div>
        <label for="field-description" class="block text-sm font-medium text-text mb-1">
          Descripción
        </label>
        <textarea
          id="field-description"
          v-model="current.description"
          data-test="field-description"
          rows="3"
          placeholder="Descripción opcional de la aplicación"
          class="w-full rounded border border-surface-0 px-3 py-2 text-sm text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary resize-y"
        />
      </div>

      <!-- Activa -->
      <div class="flex items-center gap-3">
        <input
          id="field-active"
          v-model="current.active"
          type="checkbox"
          data-test="field-active"
          class="h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
          aria-label="Aplicación activa"
        />
        <label for="field-active" class="text-sm font-medium text-text cursor-pointer">
          Activa
        </label>
      </div>

      <!-- Backend de escáner -->
      <div>
        <label for="field-scanner-backend" class="block text-sm font-medium text-text mb-1">
          Backend de escáner
        </label>
        <select
          id="field-scanner-backend"
          v-model="current.scanner_backend"
          data-test="field-scanner-backend"
          class="w-full rounded border border-surface-0 px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option
            v-for="opt in SCANNER_BACKENDS"
            :key="opt.value"
            :value="opt.value"
            :data-test="`scanner-option-${opt.value || 'none'}`"
          >
            {{ opt.label }}
          </option>
        </select>
        <p data-test="scanner-backend-note" class="mt-1.5 text-xs text-subtext">
          El escaneado web requiere un agente local (próximamente). Esta preferencia se aplicará cuando esté disponible.
        </p>
      </div>

      <!-- Transferencia automática -->
      <div class="flex items-center gap-3">
        <input
          id="field-auto-transfer"
          v-model="current.auto_transfer"
          type="checkbox"
          data-test="field-auto-transfer"
          class="h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
          aria-label="Transferencia automática"
        />
        <label for="field-auto-transfer" class="text-sm font-medium text-text cursor-pointer">
          Transferencia automática
        </label>
      </div>

      <!-- Cerrar tras transferir -->
      <div class="flex items-center gap-3">
        <input
          id="field-close-after-transfer"
          v-model="current.close_after_transfer"
          type="checkbox"
          data-test="field-close-after-transfer"
          class="h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
          aria-label="Cerrar tras transferir"
        />
        <label for="field-close-after-transfer" class="text-sm font-medium text-text cursor-pointer">
          Cerrar tras transferir
        </label>
      </div>

      <!-- Color de fondo -->
      <div>
        <label for="field-background-color" class="block text-sm font-medium text-text mb-1">
          Color de fondo
        </label>
        <div class="flex items-center gap-3">
          <input
            id="field-background-color"
            v-model="current.background_color"
            type="color"
            data-test="field-background-color"
            class="h-9 w-14 cursor-pointer rounded border border-surface-0 p-0.5"
            aria-label="Color de fondo del lote"
          />
          <span data-test="background-color-value" class="text-sm font-mono text-subtext">
            {{ current.background_color || '#000000' }}
          </span>
        </div>
      </div>

    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
