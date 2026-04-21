<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ScriptStep } from '@/api/types-pipeline'
import type { EditorHandle } from './script-editor/editor'
import { SNIPPETS, CONTEXT_VARIABLES } from '@/api/script-context-help'

const props = defineProps<{ modelValue: ScriptStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: ScriptStep] }>()

const editorHost = ref<HTMLDivElement | null>(null)
const editorHandle = shallowRef<EditorHandle | null>(null)
const editorError = ref<string | null>(null)

function patch(update: Partial<ScriptStep>): void {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

function onEntryPointBlur(ev: Event): void {
  const raw = (ev.target as HTMLInputElement).value.trim()
  const next = raw === '' ? 'process' : raw
  if (next !== props.modelValue.entry_point) {
    patch({ entry_point: next })
  }
}

onMounted(async () => {
  if (!editorHost.value) return
  try {
    const { createEditor } = await import('./script-editor/editor')
    editorHandle.value = await createEditor({
      parent: editorHost.value,
      initialDoc: props.modelValue.script,
      onChange: (doc) => patch({ script: doc }),
    })
  } catch (err) {
    console.error('[ScriptStepForm] falló la carga del editor', err)
    editorError.value = 'No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.'
  }
})

onBeforeUnmount(() => {
  editorHandle.value?.destroy()
  editorHandle.value = null
})

const snippetsOpen = ref(false)

function toggleSnippets(): void {
  snippetsOpen.value = !snippetsOpen.value
}

function applySnippet(id: string): void {
  const snippet = SNIPPETS.find((s) => s.id === id)
  if (!snippet || !editorHandle.value) return
  editorHandle.value.insertAtCursor(snippet.code)
  snippetsOpen.value = false
}

const HELP_PANEL_KEY = 'scriptEditor.helpPanelOpen'

function resolveInitialPanelOpen(): boolean {
  const stored = localStorage.getItem(HELP_PANEL_KEY)
  if (stored === 'true' || stored === 'false') return stored === 'true'
  return window.innerWidth >= 768
}

const helpPanelOpen = ref(resolveInitialPanelOpen())

function toggleHelpPanel(): void {
  helpPanelOpen.value = !helpPanelOpen.value
  localStorage.setItem(HELP_PANEL_KEY, String(helpPanelOpen.value))
}

function copyToClipboard(text: string): void {
  navigator.clipboard?.writeText(text).catch(() => {
    // silencioso: si falla, el usuario puede copiar manualmente
  })
}
</script>

<template>
  <div class="space-y-4">
    <!-- Activo -->
    <div class="flex items-center gap-2">
      <input
        id="script_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="script_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Nombre -->
    <div>
      <label for="script_label" class="block text-sm font-medium mb-1">Nombre</label>
      <input
        id="script_label"
        type="text"
        data-test="field-label"
        :value="modelValue.label"
        @input="(e) => patch({ label: (e.target as HTMLInputElement).value })"
        placeholder="Ej: Asignar roles barcode"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
    </div>

    <!-- Función -->
    <div>
      <label for="script_entry" class="block text-sm font-medium mb-1">Función</label>
      <input
        id="script_entry"
        type="text"
        data-test="field-entry-point"
        :value="modelValue.entry_point"
        @input="(e) => patch({ entry_point: (e.target as HTMLInputElement).value })"
        @blur="onEntryPointBlur"
        placeholder="process"
        title="Nombre de la función Python a ejecutar"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
      <p class="text-xs text-subtext mt-1">Nombre de la función Python a ejecutar (default: <code>process</code>).</p>
    </div>

    <!-- Editor de código + panel lateral -->
    <div>
      <div class="flex items-center justify-between mb-1">
        <label class="block text-sm font-medium">Código Python</label>
        <div class="flex items-center gap-2">
          <button
            v-if="!helpPanelOpen"
            type="button"
            data-test="help-toggle"
            @click="toggleHelpPanel"
            class="text-xs text-subtext hover:text-text border border-surface-0 rounded px-2 py-1"
          >
            Ayuda →
          </button>
          <div class="relative">
            <button
              type="button"
              data-test="snippets-button"
              @click="toggleSnippets"
              class="text-xs text-primary hover:text-primary-hover border border-primary/40 rounded px-2 py-1"
            >
              Insertar snippet ▾
            </button>
            <div
              v-if="snippetsOpen"
              class="absolute right-0 mt-1 w-80 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
            >
              <button
                v-for="snippet in SNIPPETS"
                :key="snippet.id"
                type="button"
                data-test="snippet-item"
                @click="applySnippet(snippet.id)"
                class="w-full text-left px-3 py-2 hover:bg-surface-0"
              >
                <div class="text-sm font-medium">{{ snippet.label }}</div>
                <div class="text-xs text-subtext">{{ snippet.description }}</div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="flex gap-3">
        <!-- Editor -->
        <div class="flex-1 min-w-0">
          <div
            v-if="editorError"
            class="p-4 text-sm bg-red-50 border border-red-200 rounded"
          >
            {{ editorError }}
          </div>
          <div
            v-else
            ref="editorHost"
            data-test="editor-host"
            class="border border-surface-0 rounded-md overflow-hidden"
            style="min-height: 420px; height: 420px;"
          ></div>
        </div>

        <!-- Panel lateral de ayuda -->
        <aside
          v-if="helpPanelOpen"
          data-test="help-panel"
          class="w-64 flex-shrink-0 border border-surface-0 rounded-md bg-surface-0/30 overflow-y-auto"
          style="max-height: 420px;"
        >
          <div class="flex items-center justify-between px-3 py-2 border-b border-surface-0">
            <div class="text-xs font-medium uppercase tracking-wide text-subtext">Variables</div>
            <button
              type="button"
              data-test="help-toggle"
              @click="toggleHelpPanel"
              class="text-xs text-subtext hover:text-text"
            >
              ← Ocultar
            </button>
          </div>
          <ul class="p-2 space-y-2 text-xs">
            <li v-for="v in CONTEXT_VARIABLES" :key="v.name">
              <button
                type="button"
                class="font-mono font-semibold text-primary hover:underline"
                @click="copyToClipboard(v.name)"
                :title="`Copiar «${v.name}»`"
              >{{ v.name }}</button>
              <span class="text-subtext"> — {{ v.summary }}</span>
              <ul v-if="v.members" class="pl-4 mt-1 space-y-0.5">
                <li v-for="m in v.members" :key="m.name">
                  <button
                    type="button"
                    class="font-mono text-text hover:text-primary hover:underline"
                    @click="copyToClipboard(`${v.name}.${m.name}`)"
                    :title="`Copiar «${v.name}.${m.name}»`"
                  >·&nbsp;{{ m.signature ?? m.name }}</button>
                  <span class="text-subtext"> — {{ m.description }}</span>
                </li>
              </ul>
            </li>
          </ul>
        </aside>
      </div>
    </div>
  </div>
</template>
