import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ScanFromAgentMenu from '@/components/workbench/ScanFromAgentMenu.vue'
import { useAgentStore } from '@/stores/agent'
import type { AdfStreamEvent } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  scanFlatbed: vi.fn(),
  scanAdf: vi.fn(),
}))

import { scanFlatbed, scanAdf } from '@/api/agent'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

function setStore(opts: {
  available: boolean
  paired: boolean
  scanners?: string[]
}) {
  const store = useAgentStore()
  store.available = opts.available
  store.paired = opts.paired
  // Adaptamos string[] simple del test al shape AgentScanner del store.
  store.scanners = (opts.scanners ?? []).map((name) => ({
    name,
    backend: 'sane',
    supports_native_ui: false,
  }))
  // Suprime el detect/loadScanners del onMounted en tests.
  vi.spyOn(store, 'detect').mockResolvedValue()
  vi.spyOn(store, 'loadScanners').mockResolvedValue()
  return store
}

describe('ScanFromAgentMenu — render condicional', () => {
  it('no se renderiza si el agente no está disponible', async () => {
    setStore({ available: false, paired: false })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="scan-from-agent-menu"]').exists()).toBe(
      false,
    )
  })

  it('no se renderiza si el agente está sin vincular', async () => {
    setStore({ available: true, paired: false })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="scan-from-agent-menu"]').exists()).toBe(
      false,
    )
  })

  it('no se renderiza si está vinculado pero sin escáneres', async () => {
    setStore({ available: true, paired: true, scanners: [] })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="scan-from-agent-menu"]').exists()).toBe(
      false,
    )
  })

  it('un solo escáner: muestra los 2 botones sin selector', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="scan-from-agent-menu"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="btn-flatbed"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="btn-adf"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="scanner-select"]').exists()).toBe(false)
  })

  it('múltiples escáneres: muestra el selector', async () => {
    setStore({
      available: true,
      paired: true,
      scanners: ['dev:001', 'epson:fake'],
    })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()

    const select = wrapper.find('[data-testid="scanner-select"]')
    expect(select.exists()).toBe(true)
    const opts = select.findAll('option').map((o) => o.attributes('value'))
    expect(opts).toEqual(['dev:001', 'epson:fake'])
  })
})

describe('ScanFromAgentMenu — flatbed', () => {
  it('click flatbed: scanFlatbed con scanner_name + batch_id, emite uploaded', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanFlatbed).mockResolvedValueOnce({
      created: [{ id: 100, batch_id: 42, page_index: 0 }],
      batch_page_count: 1,
    })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    expect(scanFlatbed).toHaveBeenCalledWith({
      scanner_name: 'dev:001',
      batch_id: 42,
    })
    expect(wrapper.emitted('uploaded')).toBeTruthy()
  })

  it('flatbed con error del agente: emite error con detail', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanFlatbed).mockRejectedValueOnce(new Error('paper jam'))

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')?.[0]).toEqual(['paper jam'])
    expect(wrapper.emitted('uploaded')).toBeFalsy()
  })
})

describe('ScanFromAgentMenu — ADF', () => {
  // Helper para crear async generator de eventos NDJSON.
  async function* mockAdfStream(events: AdfStreamEvent[]) {
    for (const ev of events) {
      yield ev
    }
  }

  it('ADF happy path: 2 páginas → 2 adf-progress + adf-finished + uploaded', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanAdf).mockReturnValueOnce(
      mockAdfStream([
        { event: 'started' },
        { event: 'page_uploaded', page_index: 0, page_id: 100, batch_page_count: 1 },
        { event: 'page_uploaded', page_index: 1, page_id: 101, batch_page_count: 2 },
        { event: 'completed', total: 2 },
      ]) as ReturnType<typeof scanAdf>,
    )

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    const progressEvents = wrapper.emitted('adf-progress')!
    expect(progressEvents).toHaveLength(2)
    expect(progressEvents[0][0]).toEqual({ current: 1, total: null })
    expect(progressEvents[1][0]).toEqual({ current: 2, total: null })
    expect(wrapper.emitted('adf-finished')).toBeTruthy()
    expect(wrapper.emitted('uploaded')).toBeTruthy()
    expect(wrapper.emitted('error')).toBeFalsy()
  })

  it('ADF con error mid-stream: emite las páginas previas + error + uploaded para refresco', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanAdf).mockReturnValueOnce(
      mockAdfStream([
        { event: 'started' },
        { event: 'page_uploaded', page_index: 0, page_id: 100, batch_page_count: 1 },
        { event: 'error', code: 'scan_error', detail: 'paper jam' },
      ]) as ReturnType<typeof scanAdf>,
    )

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('adf-progress')).toHaveLength(1)
    expect(wrapper.emitted('error')?.[0]).toEqual(['paper jam'])
    // La página 0 sí está en el SaaS, así que pedimos refresco.
    expect(wrapper.emitted('uploaded')).toBeTruthy()
  })

  it('ADF con error inicial (sin páginas): no emite uploaded', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanAdf).mockImplementationOnce(() => {
      // Error antes incluso del primer next() → throw fuera del stream
      async function* gen() {
        throw new Error('Escáner no existe')
        yield {} as AdfStreamEvent
      }
      return gen() as ReturnType<typeof scanAdf>
    })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')?.[0]).toEqual(['Escáner no existe'])
    expect(wrapper.emitted('uploaded')).toBeFalsy()
    expect(wrapper.emitted('adf-finished')).toBeTruthy()
  })

  it('ADF mientras escanea: ambos botones deshabilitados', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    // Stream que nunca termina hasta que lo permita el test.
    let resolveStream!: () => void
    const blocker = new Promise<void>((r) => (resolveStream = r))
    vi.mocked(scanAdf).mockReturnValueOnce(
      (async function* () {
        yield { event: 'started' } as AdfStreamEvent
        await blocker
      })() as ReturnType<typeof scanAdf>,
    )

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42 },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    expect(
      wrapper.find('[data-testid="btn-flatbed"]').attributes('disabled'),
    ).toBeDefined()
    expect(
      wrapper.find('[data-testid="btn-adf"]').attributes('disabled'),
    ).toBeDefined()

    resolveStream()
    await flushPromises()
  })
})
