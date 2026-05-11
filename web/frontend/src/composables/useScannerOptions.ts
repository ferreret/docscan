// Composable para cargar las opciones dinámicas del escáner desde el agente
// local (sprint D, hito 13).
//
// El backend ya cachea 60s server-side; aquí mantenemos un cache de módulo
// adicional indexado por scanner_name para evitar re-fetch entre aperturas
// del ScannerOptionsDialog. ``refresh: true`` invalida ambas capas (la del
// composable y la del agente vía ``?refresh=true``).
//
// Habla directamente con http://127.0.0.1:47816 (mismo patrón que useAgentStore).

import { ref } from 'vue'
import type { DeviceOptionInfo, ScannerOptionsResponse } from '@/api/types'

const AGENT_BASE_URL = 'http://127.0.0.1:47816'

// Cache de módulo: scanner_name → DeviceOptionInfo[].
const _cache = new Map<string, DeviceOptionInfo[]>()

/** Vacía el cache. Sólo para tests. */
export function _resetScannerOptionsCache(): void {
  _cache.clear()
}

export interface UseScannerOptionsReturn {
  options: ReturnType<typeof ref<DeviceOptionInfo[]>>
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
  fetch: (scannerName: string, opts?: { refresh?: boolean }) => Promise<void>
}

export function useScannerOptions() {
  const options = ref<DeviceOptionInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchOptions(
    scannerName: string,
    opts: { refresh?: boolean } = {},
  ): Promise<void> {
    error.value = null

    if (!opts.refresh) {
      const cached = _cache.get(scannerName)
      if (cached) {
        options.value = cached
        return
      }
    }

    loading.value = true
    try {
      // El backend usa path converter ``:path`` para aceptar nombres SANE
      // con ``:`` (p.ej. ``plustek:libusb:001:003``). Si los pasamos por
      // encodeURIComponent los ``:`` se convierten en ``%3A`` y el path
      // converter no matchea. Sólo escapamos caracteres realmente
      // problemáticos en URLs: espacios y reservados de query string.
      const encoded = scannerName.replace(/ /g, '%20').replace(/[?#&]/g, encodeURIComponent)
      const qs = opts.refresh ? '?refresh=true' : ''
      const url = `${AGENT_BASE_URL}/scanners/${encoded}/options${qs}`

      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
      })
      const body = await res.json().catch(() => null)
      if (!res.ok) {
        const detail = body && typeof body === 'object' && 'detail' in body
          ? String((body as { detail: unknown }).detail)
          : `HTTP ${res.status}`
        throw new Error(detail)
      }
      const payload = body as ScannerOptionsResponse
      options.value = payload.options
      _cache.set(scannerName, payload.options)
    } catch (e) {
      options.value = []
      error.value = e instanceof Error ? e.message : 'Error desconocido'
    } finally {
      loading.value = false
    }
  }

  return {
    options,
    loading,
    error,
    fetch: fetchOptions,
  }
}
