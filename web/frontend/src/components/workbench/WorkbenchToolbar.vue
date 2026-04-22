<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { BatchResponse } from '@/api/types'

const props = defineProps<{
  batch: BatchResponse
  running: boolean
  transferring: boolean
  uploading: boolean
}>()

const emit = defineEmits<{
  (e: 'upload', files: File[]): void
  (e: 'run-pipeline'): void
  (e: 'transfer'): void
  (e: 'download-zip'): void
  (e: 'delete-batch'): void
}>()

const router = useRouter()
const canTransfer = computed(() => props.batch.state === 'read' && !props.transferring && !props.running)
const busy = computed(() => props.running || props.transferring || props.uploading)

function onUpload(event: Event): void {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  emit('upload', Array.from(input.files))
  input.value = ''
}
</script>

<template>
  <header class="border-b border-surface-0 px-4 py-2 flex items-center justify-between gap-4 bg-mantle">
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="text-xs text-subtext hover:text-text inline-flex items-center gap-1"
        @click="router.push('/batches')"
      >
        ← Lotes
      </button>
      <h1 class="text-sm font-bold text-text">Lote #{{ batch.id }}</h1>
      <span class="text-xs text-subtext uppercase tracking-wide">{{ batch.state }}</span>
    </div>
    <div class="flex items-center gap-1">
      <label class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 cursor-pointer hover:bg-crust">
        ↑ Subir
        <input type="file" multiple class="hidden" :disabled="busy" @change="onUpload" />
      </label>
      <button
        type="button"
        class="bg-primary text-base text-xs px-3 py-1.5 rounded font-semibold hover:bg-primary-hover disabled:opacity-50"
        :disabled="busy || batch.page_count === 0"
        @click="emit('run-pipeline')"
      >▶ Pipeline</button>
      <button
        type="button"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50"
        :disabled="!canTransfer"
        @click="emit('transfer')"
      >↗ Transferir</button>
      <button
        type="button"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust"
        @click="emit('download-zip')"
      >↓ ZIP</button>
      <button
        type="button"
        class="bg-base text-danger text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-danger hover:text-base"
        :disabled="busy"
        @click="emit('delete-batch')"
      >Eliminar</button>
    </div>
  </header>
</template>
