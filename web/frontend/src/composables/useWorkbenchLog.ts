import { ref, computed } from 'vue'

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'
export type LogSource = 'pipeline' | 'transfer' | 'script' | 'editor' | 'user'

export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  source: LogSource
  message: string
}

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

const MAX_ENTRIES = 5000

// Singleton state (module-level)
const entries = ref<LogEntry[]>([])
const filterLevel = ref<LogLevel>('debug')

let idCounter = 0
const mkId = () => `${Date.now()}-${++idCounter}`

const append = (
  level: LogLevel,
  source: LogSource,
  message: string,
  ts?: string,
) => {
  entries.value.push({
    id: mkId(),
    timestamp: ts ?? new Date().toISOString(),
    level,
    source,
    message,
  })
  if (entries.value.length > MAX_ENTRIES) {
    entries.value.splice(0, entries.value.length - MAX_ENTRIES)
  }
}

const appendFromEvent = (ev: any) => {
  switch (ev.type) {
    case 'pipeline_started':
      append(
        'info',
        'pipeline',
        `Pipeline iniciado (${ev.page_count ?? '?'} páginas)`,
      )
      break
    case 'page_processed':
      append(
        'debug',
        'pipeline',
        `Página ${(ev.page_index ?? 0) + 1}/${ev.page_count ?? '?'} procesada`,
      )
      break
    case 'page_error':
      append(
        'error',
        'pipeline',
        `Página ${(ev.page_index ?? 0) + 1}: ${ev.error ?? ''}`,
      )
      break
    case 'pipeline_completed':
      append(
        'info',
        'pipeline',
        `Pipeline completado${ev.elapsed ? ` en ${ev.elapsed}s` : ''}`,
      )
      break
    case 'transfer_started':
      append('info', 'transfer', 'Transferencia iniciada')
      break
    case 'transfer_page':
      append(
        'debug',
        'transfer',
        `Transferida página ${(ev.page_index ?? 0) + 1}`,
      )
      break
    case 'transfer_completed':
      append('info', 'transfer', 'Transferencia completada')
      break
    case 'transfer_error':
      append('error', 'transfer', ev.error ?? 'Error en transferencia')
      break
    case 'transfer_aborted':
      append('warn', 'transfer', 'Transferencia abortada')
      break
    case 'page_updated':
      append('debug', 'editor', `Página ${ev.page_id}: ${ev.action}`)
      break
    // ignore unknown events silently
  }
}

interface PageForErrors {
  id: number
  page_index: number
  processing_errors_json: string
  script_errors_json: string
  updated_at: string
}

const loadPersistedErrors = (pages: PageForErrors[]) => {
  for (const p of pages) {
    let procErrs: unknown[] = []
    let scriptErrs: unknown[] = []
    try {
      procErrs = JSON.parse(p.processing_errors_json || '[]')
    } catch {
      /* malformed JSON: skip */
    }
    try {
      scriptErrs = JSON.parse(p.script_errors_json || '[]')
    } catch {
      /* malformed JSON: skip */
    }

    if (Array.isArray(procErrs)) {
      for (const err of procErrs) {
        append(
          'error',
          'pipeline',
          `Página ${p.page_index + 1}: ${String(err)}`,
          p.updated_at,
        )
      }
    }

    if (Array.isArray(scriptErrs)) {
      for (const err of scriptErrs) {
        const e = err as { step_id?: string; error?: string }
        const step = e.step_id ?? '?'
        const msg = e.error ?? String(err)
        append(
          'warn',
          'script',
          `Página ${p.page_index + 1} paso ${step}: ${msg}`,
          p.updated_at,
        )
      }
    }
  }
}

const clear = () => {
  entries.value = []
}

const filteredEntries = computed(() =>
  entries.value.filter(
    (e) => LEVEL_ORDER[e.level] >= LEVEL_ORDER[filterLevel.value],
  ),
)

export function useWorkbenchLog() {
  return {
    entries,
    filteredEntries,
    filterLevel,
    append,
    appendFromEvent,
    loadPersistedErrors,
    clear,
  }
}
