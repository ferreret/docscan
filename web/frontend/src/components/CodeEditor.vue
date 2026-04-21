<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { EditorHandle } from './code-editor/editor'
import type { ContextVariable, Snippet } from '@/api/script-context-help'

const props = withDefaults(defineProps<{
  modelValue: string
  contextVariables: ContextVariable[]
  snippets?: Snippet[]
  minHeight?: number
  helpPanelStorageKey?: string
}>(), {
  snippets: () => [],
  minHeight: 420,
  helpPanelStorageKey: 'codeEditor.helpPanelOpen',
})

const emit = defineEmits<{ 'update:modelValue': [doc: string] }>()

const editorHost = ref<HTMLDivElement | null>(null)
const editorHandle = shallowRef<EditorHandle | null>(null)
const editorError = ref<string | null>(null)

const snippetsOpen = ref(false)

function resolveInitialPanelOpen(): boolean {
  const stored = localStorage.getItem(props.helpPanelStorageKey)
  if (stored === 'true' || stored === 'false') return stored === 'true'
  return window.innerWidth >= 768
}
const helpPanelOpen = ref(resolveInitialPanelOpen())

function toggleHelpPanel(): void {
  helpPanelOpen.value = !helpPanelOpen.value
  localStorage.setItem(props.helpPanelStorageKey, String(helpPanelOpen.value))
}

function toggleSnippets(): void {
  snippetsOpen.value = !snippetsOpen.value
}

function applySnippet(id: string): void {
  const snippet = props.snippets.find((s) => s.id === id)
  if (!snippet || !editorHandle.value) return
  editorHandle.value.insertAtCursor(snippet.code)
  snippetsOpen.value = false
}

function copyToClipboard(text: string): void {
  navigator.clipboard?.writeText(text).catch(() => {
    // silencioso: si falla, el usuario puede copiar manualmente
  })
}

let cancelled = false
onMounted(async () => {
  if (!editorHost.value) return
  try {
    const { createEditor } = await import('./code-editor/editor')
    if (cancelled || !editorHost.value) return
    const handle = await createEditor({
      parent: editorHost.value,
      initialDoc: props.modelValue,
      contextVariables: props.contextVariables,
      onChange: (doc) => emit('update:modelValue', doc),
    })
    if (cancelled) {
      handle.destroy()
      return
    }
    editorHandle.value = handle
  } catch (err) {
    if (cancelled) return
    console.error('[CodeEditor] falló la carga del editor', err)
    editorError.value = 'No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.'
  }
})

onBeforeUnmount(() => {
  cancelled = true
  editorHandle.value?.destroy()
  editorHandle.value = null
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <label class="block text-sm font-medium">Código Python</label>
      <div class="flex items-center gap-2">
        <button
          v-if="!helpPanelOpen"
          type="button"
          data-test="help-open"
          @click="toggleHelpPanel"
          class="text-xs text-subtext hover:text-text border border-surface-0 rounded px-2 py-1"
        >
          Ayuda →
        </button>
        <div v-if="snippets.length > 0" class="relative">
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
              v-for="snippet in snippets"
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
          :style="{ minHeight: `${minHeight}px`, height: `${minHeight}px` }"
        ></div>
      </div>

      <aside
        v-if="helpPanelOpen"
        data-test="help-panel"
        class="w-64 flex-shrink-0 border border-surface-0 rounded-md bg-surface-0/30 overflow-y-auto"
        :style="{ maxHeight: `${minHeight}px` }"
      >
        <div class="flex items-center justify-between px-3 py-2 border-b border-surface-0">
          <div class="text-xs font-medium uppercase tracking-wide text-subtext">Variables</div>
          <button
            type="button"
            data-test="help-close"
            @click="toggleHelpPanel"
            class="text-xs text-subtext hover:text-text"
          >
            ← Ocultar
          </button>
        </div>
        <ul class="p-2 space-y-2 text-xs">
          <li v-for="v in contextVariables" :key="v.name">
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
</template>
