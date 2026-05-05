<script setup lang="ts">
import { useTheme, type ThemePreference } from '@/composables/useTheme'

const { preference, setPreference } = useTheme()

interface Option {
  value: ThemePreference
  label: string
  icon: string
}

const options: Option[] = [
  { value: 'light', label: 'Tema claro', icon: '☀' },
  { value: 'auto', label: 'Tema automático según el sistema', icon: '◐' },
  { value: 'dark', label: 'Tema oscuro', icon: '☾' },
]

function select(value: ThemePreference): void {
  setPreference(value)
}
</script>

<template>
  <div
    role="radiogroup"
    aria-label="Selector de tema"
    class="inline-flex rounded-md border border-surface-1 overflow-hidden"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="preference === opt.value"
      :aria-label="opt.label"
      :title="opt.label"
      class="px-2 py-1 text-xs leading-none transition-colors"
      :class="preference === opt.value
        ? 'bg-primary text-base font-semibold'
        : 'bg-mantle text-subtext hover:bg-crust hover:text-text'"
      @click="select(opt.value)"
    >
      {{ opt.icon }}
    </button>
  </div>
</template>
