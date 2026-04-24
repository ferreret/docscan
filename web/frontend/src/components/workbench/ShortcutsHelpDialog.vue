<script setup lang="ts">
import { computed } from 'vue'
import { SHORTCUTS, CATEGORY_LABELS, type ShortcutCategory } from '@/constants/shortcuts'

defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const grouped = computed(() => {
  const map: Record<ShortcutCategory, typeof SHORTCUTS> = {
    batch: [], edit: [], nav: [], zoom: [],
  }
  for (const s of SHORTCUTS) map[s.category].push(s)
  return map
})

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    @click.self="emit('close')"
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Atajos de teclado"
      tabindex="-1"
      class="bg-base text-text rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
      @keydown="onKeydown"
    >
      <div class="flex items-center justify-between px-4 py-3 border-b border-surface-1">
        <h2 class="text-lg font-semibold">Atajos de teclado</h2>
        <button
          type="button"
          class="text-text-muted hover:text-text"
          aria-label="Cerrar"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>
      <div class="p-4 space-y-4">
        <section v-for="(items, cat) in grouped" :key="cat">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-text-muted mb-2">
            {{ CATEGORY_LABELS[cat as ShortcutCategory] }}
          </h3>
          <table class="w-full">
            <tbody>
              <tr v-for="s in items" :key="`${cat}-${s.key}`" class="border-b border-surface-1 last:border-0">
                <td class="py-1 w-24">
                  <kbd class="px-2 py-0.5 bg-surface-0 rounded text-xs font-mono">{{ s.display }}</kbd>
                </td>
                <td class="py-1 text-sm">{{ s.label }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>
  </div>
</template>
