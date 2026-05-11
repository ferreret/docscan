<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import type { ApplicationResponse, BatchResponse } from "@/api/types";
import ScanFromAgentMenu from "@/components/workbench/ScanFromAgentMenu.vue";
import { useAgentStore } from "@/stores/agent";

const props = withDefaults(
  defineProps<{
    batch: BatchResponse;
    application?: ApplicationResponse | null;
    running: boolean;
    transferring: boolean;
    uploading: boolean;
    exporting?: boolean;
    scanning?: boolean;
  }>(),
  { exporting: false, scanning: false, application: null },
);

const emit = defineEmits<{
  (e: "upload", files: File[]): void;
  (e: "run-pipeline"): void;
  (e: "transfer"): void;
  (e: "download-zip"): void;
  (e: "download-local"): void;
  (e: "delete-batch"): void;
  (e: "help"): void;
  (e: "scan-uploaded"): void;
  (e: "scan-adf-progress", payload: { current: number; total: number | null }): void;
  (e: "scan-adf-finished"): void;
  (e: "scan-error", message: string): void;
}>();

const router = useRouter();
// Permitido tanto en "read" (primer envío) como en "transferred"
// (re-envío manual). Coherente con el guard del endpoint backend.
const canTransfer = computed(
  () =>
    (props.batch.state === "read" || props.batch.state === "transferred") &&
    !props.transferring &&
    !props.running,
);
const busy = computed(
  () =>
    props.running ||
    props.transferring ||
    props.uploading ||
    props.exporting ||
    props.scanning,
);

const agent = useAgentStore();
// Botón "↓ Local" sólo si el agente está detectado y vinculado.
// El operario sin agente sigue teniendo "↓ ZIP" para descargar al
// navegador en su lugar.
const canDownloadLocal = computed(
  () => agent.available && agent.paired && props.batch.page_count > 0,
);

function onUpload(event: Event): void {
  const input = event.target as HTMLInputElement;
  if (!input.files?.length) return;
  emit("upload", Array.from(input.files));
  input.value = "";
}
</script>

<template>
  <header
    class="border-b border-surface-0 px-4 py-2 flex items-center justify-between gap-4 bg-mantle"
  >
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="text-xs text-subtext hover:text-text inline-flex items-center gap-1"
        @click="router.push('/batches')"
      >
        ← Lotes
      </button>
      <h1 class="text-sm font-bold text-text">Lote #{{ batch.id }}</h1>
      <span class="text-xs text-subtext uppercase tracking-wide">{{
        batch.state
      }}</span>
    </div>
    <div class="flex items-center gap-1">
      <label
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 cursor-pointer hover:bg-crust"
      >
        ↑ Subir
        <input
          type="file"
          multiple
          class="hidden"
          :disabled="busy"
          @change="onUpload"
        />
      </label>
      <ScanFromAgentMenu
        :batchId="batch.id"
        :disabled="busy"
        :application="application"
        @uploaded="emit('scan-uploaded')"
        @adf-progress="(p) => emit('scan-adf-progress', p)"
        @adf-finished="emit('scan-adf-finished')"
        @error="(m) => emit('scan-error', m)"
      />
      <button
        type="button"
        class="bg-primary text-base text-xs px-3 py-1.5 rounded font-semibold hover:bg-primary-hover disabled:opacity-50"
        :disabled="busy || batch.page_count === 0"
        @click="emit('run-pipeline')"
      >
        ▶ Pipeline
      </button>
      <button
        type="button"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50"
        :disabled="!canTransfer"
        @click="emit('transfer')"
      >
        ↗ Transferir
      </button>
      <button
        type="button"
        data-testid="btn-zip"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50 inline-flex items-center gap-1.5"
        :disabled="exporting"
        @click="emit('download-zip')"
      >
        <span
          v-if="exporting"
          class="inline-block w-3 h-3 border-2 border-text border-t-transparent rounded-full animate-spin"
        ></span>
        <span>{{ exporting ? "Generando…" : "↓ ZIP" }}</span>
      </button>
      <button
        v-if="canDownloadLocal"
        type="button"
        data-testid="btn-download-local"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50"
        :disabled="busy"
        title="Descarga el lote al PC del operario vía el agente local"
        @click="emit('download-local')"
      >
        ↓ Local
      </button>
      <button
        type="button"
        class="bg-base text-danger text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-danger hover:text-base"
        :disabled="busy"
        @click="emit('delete-batch')"
      >
        Eliminar
      </button>
      <button
        type="button"
        class="bg-base text-subtext text-xs px-2.5 py-1.5 rounded border border-surface-1 hover:bg-crust hover:text-text font-semibold"
        title="Ayuda (? o H)"
        @click="emit('help')"
      >
        ?
      </button>
    </div>
  </header>
</template>
