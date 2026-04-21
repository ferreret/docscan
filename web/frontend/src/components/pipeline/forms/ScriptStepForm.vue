<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ScriptStep } from '@/api/types-pipeline'
import type { EditorHandle } from './script-editor/editor'
import { SNIPPETS } from '@/api/script-context-help'

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

    <!-- Editor de código -->
    <div>
      <div class="flex items-center justify-between mb-1">
        <label class="block text-sm font-medium">Código Python</label>
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
  </div>
</template>
