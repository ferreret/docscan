<script setup lang="ts">
import { computed, onMounted, ref, onBeforeUnmount, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'
import AppHeader from '@/components/AppHeader.vue'
import CodeEditor from '@/components/CodeEditor.vue'

const route = useRoute()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

const originalEvents = ref<Record<string, string>>({})
const events = ref<Record<string, string>>({})
const currentEventName = ref<string>(EVENT_DEFINITIONS[0].name)
const saving = ref(false)
const saveError = ref<string | null>(null)

const currentEvent = computed(() =>
  EVENT_DEFINITIONS.find((e) => e.name === currentEventName.value)!,
)

const currentEditorValue = computed(() => {
  const stored = events.value[currentEventName.value]
  return stored !== undefined ? stored : currentEvent.value.template
})

const hasChanges = computed(() => {
  const keys = new Set([
    ...Object.keys(originalEvents.value),
    ...Object.keys(events.value),
  ])
  for (const k of keys) {
    if ((originalEvents.value[k] ?? '') !== (events.value[k] ?? '')) return true
  }
  return false
})

function parseEventsJson(raw: string): Record<string, string> {
  try {
    const parsed = JSON.parse(raw || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, string>
    }
    return {}
  } catch (err) {
    console.warn('[EventsEditorView] events_json inválido, usando {}', err)
    return {}
  }
}

function onEditorChange(doc: string): void {
  // Si el doc coincide con el template y no había código previamente,
  // no persistir (mantiene el evento como "sin código").
  if (doc === currentEvent.value.template && originalEvents.value[currentEventName.value] === undefined) {
    if (events.value[currentEventName.value] !== undefined) {
      const next = { ...events.value }
      delete next[currentEventName.value]
      events.value = next
    }
    return
  }
  // Si el código está vacío tras trim, eliminar la clave (match desktop).
  if (doc.trim() === '') {
    if (events.value[currentEventName.value] !== undefined) {
      const next = { ...events.value }
      delete next[currentEventName.value]
      events.value = next
    }
    return
  }
  events.value = { ...events.value, [currentEventName.value]: doc }
}

function selectEvent(name: string): void {
  currentEventName.value = name
}

function hasCode(name: string): boolean {
  return (events.value[name] ?? '').trim().length > 0
}

async function onSave(): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, {
      events_json: JSON.stringify(events.value),
    })
    originalEvents.value = { ...events.value }
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

function onUndo(): void {
  events.value = { ...originalEvents.value }
}

function onBeforeUnload(ev: BeforeUnloadEvent): void {
  if (hasChanges.value) {
    ev.preventDefault()
    ev.returnValue = ''
  }
}

let fetchedForId: number | null = null

async function loadFromStore(id: number): Promise<void> {
  if (fetchedForId === id) return
  fetchedForId = id
  await appStore.fetchOne(id)
  const parsed = parseEventsJson(appStore.current?.events_json ?? '{}')
  originalEvents.value = parsed
  events.value = { ...parsed }
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
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

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

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
          data-test="undo-events"
          :disabled="!hasChanges"
          @click="onUndo"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2 disabled:opacity-50"
        >
          Deshacer
        </button>
        <button
          type="button"
          data-test="save-events"
          :disabled="!hasChanges || saving"
          @click="onSave"
          class="text-[13px] bg-primary text-white rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <div v-if="saveError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-danger">
      {{ saveError }}
    </div>

    <div class="flex gap-4">
      <!-- Sidebar -->
      <aside class="w-64 flex-shrink-0 bg-white rounded-md border border-surface-0 overflow-y-auto" style="max-height: 560px;">
        <div class="px-3 py-2 border-b border-surface-0 text-xs font-medium uppercase tracking-wide text-subtext">
          Eventos
        </div>
        <ul>
          <li
            v-for="ev in EVENT_DEFINITIONS"
            :key="ev.name"
            data-test="event-item"
            role="button"
            tabindex="0"
            :aria-current="currentEventName === ev.name ? 'true' : undefined"
            @click="selectEvent(ev.name)"
            @keydown.enter.prevent="selectEvent(ev.name)"
            @keydown.space.prevent="selectEvent(ev.name)"
            :class="[
              'cursor-pointer px-3 py-2 border-b border-surface-0 last:border-b-0',
              currentEventName === ev.name ? 'bg-primary-soft text-primary font-semibold' : 'text-text hover:bg-surface-0',
            ]"
          >
            <div class="flex items-center gap-2">
              <span
                v-if="hasCode(ev.name)"
                data-test="event-indicator-active"
                :data-event="ev.name"
                class="w-2 h-2 rounded-full bg-success"
              ></span>
              <span v-else class="w-2 h-2 rounded-full bg-surface-0"></span>
              <span class="font-mono text-[13px]">{{ ev.name }}</span>
            </div>
            <div class="text-xs text-subtext mt-0.5 ml-4">{{ ev.description }}</div>
          </li>
        </ul>
      </aside>

      <!-- Editor -->
      <div class="flex-1 min-w-0">
        <CodeEditor
          :key="currentEventName"
          :model-value="currentEditorValue"
          :context-variables="currentEvent.contextVariables"
          help-panel-storage-key="eventsEditor.helpPanelOpen"
          :min-height="460"
          @update:model-value="onEditorChange"
        />
        <p class="text-xs text-subtext mt-2">
          <span class="font-semibold">Firma:</span>
          <code class="font-mono">{{ currentEvent.signature }}</code>
          — {{ currentEvent.description }}
        </p>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
