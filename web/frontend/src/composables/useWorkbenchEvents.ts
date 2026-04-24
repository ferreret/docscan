import * as client from '@/api/client'
import type { EventFireIn, EventResult } from '@/api/types'

interface EventsOptions {
  onApplyPageFields?: (pageId: number, fields: Record<string, unknown>) => void
  onApplyBatchFields?: (fields: Record<string, unknown>) => void
  onLogs?: (logs: { level: string; message: string }[]) => void
}

const THROTTLE_MS = 100

/**
 * Dispara eventos lifecycle del workbench contra el backend.
 * - fireSync: POST con await, devuelve EventResult.
 * - fireAsync: POST sin await. Aplica throttle por (event, page_id) para
 *   evitar doble dispatch en mismo frame.
 */
export function useWorkbenchEvents(batchId: number, options: EventsOptions = {}) {
  const lastFired = new Map<string, number>()

  function throttleKey(name: string, payload: EventFireIn): string {
    return `${name}:${payload.page_id ?? 0}`
  }

  function applyResult(result: EventResult, payload: EventFireIn): void {
    if (result.fields_updated && Object.keys(result.fields_updated).length && payload.page_id) {
      options.onApplyPageFields?.(payload.page_id, result.fields_updated)
    }
    if (result.batch_fields_updated && Object.keys(result.batch_fields_updated).length) {
      options.onApplyBatchFields?.(result.batch_fields_updated)
    }
    if (result.logs && result.logs.length) {
      options.onLogs?.(result.logs)
    }
  }

  async function fireSync(name: string, payload: EventFireIn = {}): Promise<EventResult> {
    try {
      const res = await client.fireEvent(batchId, name, payload)
      applyResult(res, payload)
      return res
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return {
        executed: false, result: null, cancel: false, target_page_id: null,
        fields_updated: {}, batch_fields_updated: {}, logs: [], error: msg,
      }
    }
  }

  function fireAsync(name: string, payload: EventFireIn = {}): void {
    const k = throttleKey(name, payload)
    const now = Date.now()
    const last = lastFired.get(k) ?? 0
    if (now - last < THROTTLE_MS) return
    lastFired.set(k, now)
    client.fireEvent(batchId, name, payload)
      .then((res) => applyResult(res, payload))
      .catch((e) => {
        const msg = e instanceof Error ? e.message : String(e)
        options.onLogs?.([{ level: 'error', message: `Evento ${name}: ${msg}` }])
      })
  }

  return { fireSync, fireAsync }
}
