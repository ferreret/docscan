// Store del agente local (sprint cliente local web, hito 9).
//
// Habla con dos backends distintos:
// - El SaaS (mismo origen, vía `api`) para ``POST /api/agent/pair-init``,
//   que devuelve el código de pairing único.
// - El agente local (otro origen, vía ``fetch`` directo a ``http://127.0.0.1:47816``)
//   para ``GET /status``, ``POST /pair``, ``GET /scanners``.
//
// El SaaS y el agente NO comparten origen, así que las peticiones al
// agente requieren CORS (ver ``docscan_local_agent/main.py``). El
// agent_token nunca pasa por aquí — lo persiste el agente en disco con
// permisos 0600.

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type {
  AgentStatus,
  AgentPairResponse,
  PairInitResponse,
} from '@/api/types'

const AGENT_BASE_URL = 'http://127.0.0.1:47816'

async function agentFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${AGENT_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body
      ? String((body as { detail: unknown }).detail)
      : `HTTP ${res.status}`
    throw new Error(detail)
  }
  return body as T
}

export const useAgentStore = defineStore('agent', () => {
  const available = ref(false)
  const paired = ref(false)
  const status = ref<AgentStatus | null>(null)
  const scanners = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const displayName = computed(() => status.value?.device_name ?? null)

  async function detect(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await agentFetch<AgentStatus>('/status')
      status.value = data
      available.value = true
      paired.value = data.paired
    } catch (e) {
      // Cualquier error (red, 5xx, JSON inválido) → agente no disponible.
      available.value = false
      paired.value = false
      status.value = null
      error.value = e instanceof Error ? e.message : 'Error desconocido'
    } finally {
      loading.value = false
    }
  }

  async function pair(deviceName: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      // 1. SaaS genera el código y reserva el AgentDevice.
      const init = await api.post<PairInitResponse>('/agent/pair-init', {
        name: deviceName,
      })

      // 2. Agente canjea el código contra el SaaS y persiste el token.
      await agentFetch<AgentPairResponse>('/pair', {
        method: 'POST',
        body: JSON.stringify({
          saas_url: window.location.origin,
          code: init.code,
        }),
      })

      // 3. Refresca el status para reflejar paired=true.
      await detect()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al vincular'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loadScanners(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      scanners.value = await agentFetch<string[]>('/scanners')
    } catch (e) {
      scanners.value = []
      error.value = e instanceof Error ? e.message : 'Error al listar escáneres'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    available.value = false
    paired.value = false
    status.value = null
    scanners.value = []
    error.value = null
  }

  return {
    available,
    paired,
    status,
    scanners,
    loading,
    error,
    displayName,
    detect,
    pair,
    loadScanners,
    reset,
  }
})
