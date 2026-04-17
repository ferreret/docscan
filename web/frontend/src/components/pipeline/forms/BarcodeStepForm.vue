<script setup lang="ts">
import { computed, watch } from 'vue'
import type { BarcodeStep } from '@/api/types-pipeline'
import { SYMBOLOGIES } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: BarcodeStep }>()
const emit = defineEmits<{
  'update:modelValue': [step: BarcodeStep]
  'validity-change': [valid: boolean]
}>()

function patch(update: Partial<BarcodeStep>): void {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

const regexError = computed(() => {
  if (!props.modelValue.regex) return ''
  try {
    new RegExp(props.modelValue.regex)
    return ''
  } catch (e) {
    return (e as Error).message
  }
})

watch(regexError, (err) => emit('validity-change', !err), { immediate: true })

function toggleSymbology(sym: string) {
  const list = props.modelValue.symbologies
  const next = list.includes(sym)
    ? list.filter((s) => s !== sym)
    : [...list, sym]
  patch({ symbologies: next })
}

function toggleOrientation(ori: string) {
  const list = props.modelValue.orientations
  const next = list.includes(ori)
    ? list.filter((o) => o !== ori)
    : [...list, ori]
  patch({ orientations: next })
}

function toggleCustomRegion(v: boolean) {
  patch({ window: v ? [0, 0, 100, 100] : null })
}

function updateWindowAt(idx: number, value: number) {
  const w = props.modelValue.window!
  const next: [number, number, number, number] = [w[0], w[1], w[2], w[3]]
  next[idx] = value
  patch({ window: next })
}
</script>

<template>
  <div class="space-y-4">
    <!-- Enabled -->
    <div class="flex items-center gap-2">
      <input
        id="enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="enabled" class="text-sm">Activo</label>
    </div>

    <!-- Engine -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Motor</label>
      <select
        :value="modelValue.engine"
        @change="(e) => patch({ engine: (e.target as HTMLSelectElement).value as 'motor1' | 'motor2' })"
        class="w-full border rounded-md px-2 py-1.5 text-sm"
      >
        <option value="motor1">Motor 1 (pyzbar)</option>
        <option value="motor2">Motor 2 (zxing-cpp)</option>
      </select>
    </div>

    <!-- Symbologies -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Simbologías <span class="text-subtext normal-case">(vacío = todas)</span>
      </label>
      <div class="grid grid-cols-3 gap-1.5">
        <label
          v-for="sym in SYMBOLOGIES"
          :key="sym"
          class="flex items-center gap-1.5 text-xs cursor-pointer"
        >
          <input
            type="checkbox"
            :checked="modelValue.symbologies.includes(sym)"
            @change="toggleSymbology(sym)"
          />
          {{ sym }}
        </label>
      </div>
    </div>

    <!-- Regex -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Regex <span class="text-subtext normal-case">(vacío = sin filtro)</span>
      </label>
      <input
        :value="modelValue.regex"
        @input="(e) => patch({ regex: (e.target as HTMLInputElement).value })"
        type="text"
        class="w-full border rounded-md px-2 py-1.5 text-sm font-mono"
        :class="{ 'border-danger': regexError }"
        placeholder="^DOC-\d+$"
      />
      <p v-if="regexError" class="text-[11px] text-danger mt-1">
        Regex inválida: {{ regexError }}
      </p>
      <div class="flex items-center gap-2 mt-2">
        <input
          id="regex_inc_sym"
          type="checkbox"
          :checked="modelValue.regex_include_symbology"
          @change="(e) => patch({ regex_include_symbology: (e.target as HTMLInputElement).checked })"
        />
        <label for="regex_inc_sym" class="text-xs">
          Incluir simbología en el match
        </label>
      </div>
    </div>

    <!-- Orientations -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Orientaciones</label>
      <div class="flex gap-4">
        <label class="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            :checked="modelValue.orientations.includes('horizontal')"
            @change="toggleOrientation('horizontal')"
          />
          Horizontal
        </label>
        <label class="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            :checked="modelValue.orientations.includes('vertical')"
            @change="toggleOrientation('vertical')"
          />
          Vertical
        </label>
      </div>
    </div>

    <!-- Quality threshold -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Umbral de calidad (0.0 - 1.0)
      </label>
      <input
        :value="modelValue.quality_threshold"
        @input="(e) => patch({ quality_threshold: Number((e.target as HTMLInputElement).value) })"
        type="number"
        min="0"
        max="1"
        step="0.01"
        class="w-full border rounded-md px-2 py-1.5 text-sm"
      />
    </div>

    <!-- Region -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Región</label>
      <div class="flex items-center gap-2 mb-2">
        <input
          id="custom_region"
          type="checkbox"
          :checked="modelValue.window !== null"
          @change="(e) => toggleCustomRegion((e.target as HTMLInputElement).checked)"
        />
        <label for="custom_region" class="text-sm">
          Usar región personalizada (en píxeles)
        </label>
      </div>
      <div v-if="modelValue.window" class="grid grid-cols-4 gap-2">
        <div v-for="(label, idx) in ['x', 'y', 'w', 'h']" :key="label">
          <label class="text-[11px] text-subtext">{{ label }}</label>
          <input
            type="number"
            :value="modelValue.window[idx]"
            @input="(e) => updateWindowAt(idx, Number((e.target as HTMLInputElement).value))"
            class="w-full border rounded-md px-2 py-1 text-sm"
          />
        </div>
      </div>
    </div>
  </div>
</template>
