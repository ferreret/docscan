import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAgentStore } from '@/stores/agent'
import type {
  AgentStatus,
  AgentPairResponse,
  PairInitResponse,
} from '@/api/types'

// Mock del cliente del SaaS — el store usa api.post para /api/agent/pair-init.
vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  ApiError: class extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(detail)
      this.status = status
      this.detail = detail
    }
  },
}))

import { api } from '@/api/client'

const STATUS_UNPAIRED: AgentStatus = {
  name: 'docscan-local-agent',
  version: '0.1.0',
  paired: false,
  device_name: null,
  user_email: null,
  tenant_name: null,
}

const STATUS_PAIRED: AgentStatus = {
  name: 'docscan-local-agent',
  version: '0.1.0',
  paired: true,
  device_name: 'Portátil Ana',
  user_email: 'ana@example.com',
  tenant_name: 'TecnoMedia',
}

const PAIR_INIT: PairInitResponse = {
  device_id: 7,
  code: 'ABCDEF23',
  expires_at: '2026-05-08T15:00:00Z',
}

const AGENT_PAIR: AgentPairResponse = {
  paired: true,
  device_id: 7,
  device_name: 'Portátil Ana',
  user_email: 'ana@example.com',
  tenant_name: 'TecnoMedia',
  paired_at: '2026-05-08T14:55:00Z',
}

function mockFetchOnce(payload: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn().mockResolvedValueOnce({
    ok,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  })
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
  return fetchMock
}

function mockFetchSequence(...responses: { payload: unknown; ok?: boolean; status?: number }[]) {
  const fetchMock = vi.fn()
  for (const r of responses) {
    fetchMock.mockResolvedValueOnce({
      ok: r.ok ?? true,
      status: r.status ?? 200,
      json: async () => r.payload,
      text: async () => JSON.stringify(r.payload),
    })
  }
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
  return fetchMock
}

describe('useAgentStore — detect()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('detect agente sin vincular: available=true paired=false status poblado', async () => {
    mockFetchOnce(STATUS_UNPAIRED)
    const store = useAgentStore()

    await store.detect()

    expect(store.available).toBe(true)
    expect(store.paired).toBe(false)
    expect(store.status).toEqual(STATUS_UNPAIRED)
    expect(store.error).toBeNull()
  })

  it('detect agente vinculado: paired=true con metadatos', async () => {
    mockFetchOnce(STATUS_PAIRED)
    const store = useAgentStore()

    await store.detect()

    expect(store.available).toBe(true)
    expect(store.paired).toBe(true)
    expect(store.status?.device_name).toBe('Portátil Ana')
  })

  it('detect agente caído: available=false, error poblado', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch'))
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
    const store = useAgentStore()

    await store.detect()

    expect(store.available).toBe(false)
    expect(store.paired).toBe(false)
    expect(store.status).toBeNull()
    // El error queda en el store por si la vista quiere mostrarlo, aunque
    // el caso "agente caído" se renderiza con su placeholder específico.
    expect(store.error).toContain('Failed to fetch')
  })

  it('detect respuesta no-200 trata como agente no disponible', async () => {
    mockFetchOnce({ detail: 'oops' }, false, 500)
    const store = useAgentStore()

    await store.detect()

    expect(store.available).toBe(false)
  })
})

describe('useAgentStore — pair()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('pair: pair-init SaaS → POST /pair agente → re-detect', async () => {
    // 1. /api/agent/pair-init (vía api.post)
    vi.mocked(api.post).mockResolvedValueOnce(PAIR_INIT)
    // 2. POST localhost:47816/pair → AgentPairResponse
    // 3. GET localhost:47816/status → STATUS_PAIRED (re-detect tras pair)
    const fetchMock = mockFetchSequence(
      { payload: AGENT_PAIR, status: 200 },
      { payload: STATUS_PAIRED, status: 200 },
    )

    const store = useAgentStore()
    await store.pair('Portátil Ana')

    expect(api.post).toHaveBeenCalledWith('/agent/pair-init', { name: 'Portátil Ana' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    // Primera llamada al agente: POST /pair con saas_url + code.
    const pairUrl = fetchMock.mock.calls[0][0] as string
    const pairInit = fetchMock.mock.calls[0][1] as RequestInit
    expect(pairUrl).toMatch(/127\.0\.0\.1:47816\/pair$/)
    expect(pairInit.method).toBe('POST')
    const pairBody = JSON.parse(pairInit.body as string)
    expect(pairBody.code).toBe('ABCDEF23')
    expect(pairBody.saas_url).toBe(window.location.origin)
    // Tras pair, store refleja paired=true
    expect(store.paired).toBe(true)
    expect(store.status?.device_name).toBe('Portátil Ana')
  })

  it('pair: si pair-init del SaaS falla, no llega a hablar con el agente', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('401 unauthorized'))
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const store = useAgentStore()
    await expect(store.pair('Portátil Ana')).rejects.toThrow()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pair: si el agente rechaza el código, propaga el error', async () => {
    vi.mocked(api.post).mockResolvedValueOnce(PAIR_INIT)
    mockFetchOnce({ detail: 'Código no válido' }, false, 404)

    const store = useAgentStore()
    await expect(store.pair('Portátil Ana')).rejects.toThrow(/no v[áa]lido/i)
  })
})

describe('useAgentStore — loadScanners()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadScanners: GET /scanners y popula la lista', async () => {
    mockFetchOnce({
      backend: 'sane',
      scanners: [
        { name: 'dev:001', backend: 'sane', supports_native_ui: false },
        { name: 'epson:fake', backend: 'sane', supports_native_ui: false },
      ],
    })
    const store = useAgentStore()

    await store.loadScanners()

    expect(store.scanners).toEqual([
      { name: 'dev:001', backend: 'sane', supports_native_ui: false },
      { name: 'epson:fake', backend: 'sane', supports_native_ui: false },
    ])
    expect(store.scannerNames).toEqual(['dev:001', 'epson:fake'])
  })

  it('loadScanners: store expone supports_native_ui via findScanner()', async () => {
    mockFetchOnce({
      backend: 'twain',
      scanners: [
        { name: 'TWAIN: Canon DR-M160', backend: 'twain', supports_native_ui: true },
      ],
    })
    const store = useAgentStore()
    await store.loadScanners()

    const found = store.findScanner('TWAIN: Canon DR-M160')
    expect(found?.supports_native_ui).toBe(true)
    expect(store.findScanner('inexistente')).toBeUndefined()
  })

  it('loadScanners: 503 sin backends → scanners=[] y error poblado', async () => {
    mockFetchOnce({ detail: 'No hay backends de escáner disponibles' }, false, 503)
    const store = useAgentStore()

    await store.loadScanners()

    expect(store.scanners).toEqual([])
    expect(store.error).toContain('backends')
  })
})
