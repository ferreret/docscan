<script setup lang="ts">
defineProps<{ visible: boolean; barcodeValue: string }>()
const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'close'): void
}>()
</script>

<template>
  <div
    v-if="visible"
    data-testid="overlay"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div class="bg-mantle border border-surface-1 rounded-lg p-6 min-w-[360px] shadow-lg">
      <h3 class="text-lg font-semibold mb-3 text-text">Eliminar barcode</h3>
      <p class="mb-5 text-text">
        ¿Eliminar el barcode <strong>{{ barcodeValue }}</strong>?
      </p>
      <div class="flex justify-end gap-2">
        <button
          data-testid="cancel"
          type="button"
          class="px-3 py-1.5 border border-surface-1 rounded hover:bg-crust text-text"
          @click="emit('close')"
        >Cancelar</button>
        <button
          data-testid="confirm"
          type="button"
          class="px-3 py-1.5 bg-danger text-base rounded hover:opacity-90"
          @click="emit('confirm')"
        >Eliminar</button>
      </div>
    </div>
  </div>
</template>
