<script setup lang="ts">
import type { ScriptStep } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: ScriptStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: ScriptStep] }>()

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

    <!-- Placeholder para el editor (se implementa en Task 7) -->
    <div data-test="editor-placeholder" class="text-xs text-subtext italic">
      (editor de código — pendiente de implementar)
    </div>
  </div>
</template>
