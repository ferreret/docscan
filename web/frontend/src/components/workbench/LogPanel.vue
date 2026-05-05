<script setup lang="ts">
import { useWorkbenchLog, type LogLevel } from '@/composables/useWorkbenchLog'

const log = useWorkbenchLog()

const LEVEL_COLOR: Record<LogLevel, string> = {
  debug: 'text-subtext',
  info: 'text-text',
  warn: 'text-warning',
  error: 'text-danger',
}

const formatTime = (iso: string): string => {
  try {
    const d = new Date(iso)
    // Forzar 24h y locale es-ES para evitar AM/PM aunque el navegador
    // tenga otro locale por defecto (issue #36).
    return d.toLocaleTimeString('es-ES', { hour12: false })
  } catch {
    return iso.slice(11, 19)
  }
}

const formatEntriesCount = (n: number): string =>
  n === 1 ? '1 entrada' : `${n} entradas`
</script>

<template>
  <div class="h-full flex flex-col bg-base">
    <!-- Header -->
    <div class="flex items-center gap-2 p-2 border-b border-surface-0 text-xs">
      <label class="flex items-center gap-1">
        <span class="text-subtext">Nivel:</span>
        <select
          data-testid="filter-level"
          v-model="log.filterLevel.value"
          class="border border-surface-1 rounded px-2 py-0.5 bg-base text-text"
        >
          <option value="debug">Debug+</option>
          <option value="info">Info+</option>
          <option value="warn">Warn+</option>
          <option value="error">Error</option>
        </select>
      </label>
      <button
        data-testid="btn-clear"
        type="button"
        class="ml-auto px-2 py-0.5 border border-surface-1 rounded hover:bg-crust text-text"
        @click="log.clear()"
      >
        Limpiar
      </button>
      <span data-testid="entries-count" class="text-subtext">
        {{ formatEntriesCount(log.filteredEntries.value.length) }}
      </span>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto font-mono text-xs p-2">
      <div
        v-for="e in log.filteredEntries.value"
        :key="e.id"
        data-testid="log-entry"
        :data-level="e.level"
        :class="LEVEL_COLOR[e.level]"
        class="py-0.5 whitespace-pre-wrap break-words"
      >
        <span class="text-subtext">{{ formatTime(e.timestamp) }}</span>
        <span class="mx-1 uppercase text-[10px]">{{ e.level }}</span>
        <span class="text-subtext">·{{ e.source }}·</span>
        <span>{{ e.message }}</span>
      </div>
      <p
        v-if="log.filteredEntries.value.length === 0"
        class="text-subtext italic text-center mt-4"
      >
        Sin eventos aún. Los mensajes aparecerán aquí mientras procesas el lote.
      </p>
    </div>
  </div>
</template>
