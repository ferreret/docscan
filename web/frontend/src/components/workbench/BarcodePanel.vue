<script setup lang="ts">
import type { BarcodeResponse } from '@/api/types'

withDefaults(defineProps<{
  barcodes: BarcodeResponse[]
  pageCounters: { total: number; withBarcode: number; separators: number; needsReview: number }
  readOnly?: boolean
}>(), {
  readOnly: false,
})

const emit = defineEmits<{
  (e: 'add-barcode'): void
  (e: 'delete-barcode', id: number): void
}>()

const COLORS = ['#1e66f5', '#40a02b', '#df8e1d', '#d20f39', '#8839ef', '#179299', '#e64553', '#dd7878']

function colorFor(idx: number): string {
  return COLORS[idx % COLORS.length]
}
</script>

<template>
  <section class="h-full flex flex-col bg-mantle border-l border-surface-0">
    <header class="px-3 py-2 border-b border-surface-0 flex items-center justify-between text-xs">
      <div class="flex items-center gap-2">
        <h2 class="font-semibold text-text uppercase tracking-wide">Barcodes</h2>
        <button
          v-if="!readOnly"
          data-testid="btn-add-barcode"
          type="button"
          class="ml-2 px-2 py-0.5 bg-primary text-base rounded text-xs hover:opacity-90"
          @click="emit('add-barcode')"
        >+ Añadir</button>
      </div>
      <div class="flex gap-3 text-subtext">
        <span data-test="counter-total">Páginas: {{ pageCounters.total }}</span>
        <span data-test="counter-with-barcode">Con barcode: {{ pageCounters.withBarcode }}</span>
        <span data-test="counter-separators">Separadores: {{ pageCounters.separators }}</span>
        <span data-test="counter-needs-review">Revisión: {{ pageCounters.needsReview }}</span>
      </div>
    </header>

    <div class="flex-1 overflow-auto">
      <table v-if="barcodes.length > 0" class="w-full text-xs">
        <thead class="bg-crust text-subtext uppercase">
          <tr>
            <th class="w-6"></th>
            <th class="text-left px-2 py-1.5">Valor</th>
            <th class="text-left px-2 py-1.5">Símbolo</th>
            <th class="text-left px-2 py-1.5">Motor</th>
            <th class="text-left px-2 py-1.5">Rol</th>
            <th v-if="!readOnly" class="w-6"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(bc, idx) in barcodes" :key="bc.id" class="border-t border-surface-0">
            <td class="px-2"><span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: colorFor(idx) }"></span></td>
            <td class="px-2 py-1 text-text font-mono">{{ bc.value }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.symbology }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.engine }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.role || '—' }}</td>
            <td v-if="!readOnly" class="px-1">
              <button
                :data-testid="`btn-delete-bc-${bc.id}`"
                type="button"
                class="text-danger hover:bg-crust rounded px-1"
                title="Eliminar"
                @click="emit('delete-barcode', bc.id)"
              >×</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-center text-subtext text-xs py-6">Sin barcodes en esta página</p>
    </div>
  </section>
</template>
