import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import ScanFromAgentMenu from '@/components/workbench/ScanFromAgentMenu.vue'
import { useAgentStore } from '@/stores/agent'
import type { AdfStreamEvent } from '@/api/agent'
import type { ApplicationResponse } from '@/api/types'

vi.mock('@/api/agent', () => ({
  scanFlatbed: vi.fn(),
  scanAdf: vi.fn(),
}))

// Mock del store applications: el componente lo usa para PATCHear
// scan_defaults_json al pulsar "Recordar para esta aplicación".
const mockUpdate = vi.fn()
vi.mock('@/stores/applications', () => ({
  useApplicationsStore: () => ({ update: mockUpdate }),
}))

// Stub del ScannerOptionsDialog: el dialog ya tiene 18 tests propios.
// Aquí sólo verificamos que el menú lo invoca con los props correctos
// y reacciona a los eventos. El stub expone botones para emitir
// submit/cancel/save-defaults a comando.
vi.mock('@/components/workbench/ScannerOptionsDialog.vue', () => ({
  default: defineComponent({
    name: 'ScannerOptionsDialog',
    props: {
      visible: { type: Boolean, required: true },
      scannerName: { type: String, required: true },
      initialDefaults: { type: Object, required: true },
      canSaveDefaults: { type: Boolean, required: true },
    },
    emits: ['submit', 'save-defaults', 'close'],
    template: `
      <div v-if="visible"
           data-testid="dialog-stub"
           :data-scanner="scannerName"
           :data-can-save="String(canSaveDefaults)"
           :data-initial="JSON.stringify(initialDefaults)">
        <button data-testid="dialog-submit"
                @click="$emit('submit', { resolution: 600, mode: 'Gray' })">submit</button>
        <button data-testid="dialog-cancel" @click="$emit('close')">cancel</button>
        <button data-testid="dialog-save-defaults"
                @click="$emit('save-defaults', { resolution: 600, mode: 'Gray' })">save</button>
      </div>
    `,
  }),
}))

import { scanFlatbed, scanAdf } from '@/api/agent'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

afterEach(() => {
  mockUpdate.mockReset()
})

// Builder de ApplicationResponse con defaults razonables.
function makeApp(overrides: Partial<ApplicationResponse> = {}): ApplicationResponse {
  return {
    id: 7,
    name: 'App',
    description: '',
    active: true,
    output_format: 'pdf',
    created_at: '2026-05-08T10:00:00Z',
    tenant_id: 1,
    pipeline_json: '[]',
    events_json: '{}',
    transfer_json: '{}',
    batch_fields_json: '[]',
    index_fields_json: '[]',
    auto_transfer: false,
    close_after_transfer: false,
    background_color: '',
    default_tab: 'workbench',
    scanner_backend: '',
    image_config_json: '{}',
    ai_config_json: '{}',
    scan_defaults_json: '{}',
    scan_show_dialog: true,
    updated_at: '2026-05-08T10:00:00Z',
    ...overrides,
  }
}

function setStore(opts: {
  available: boolean
  paired: boolean
  scanners?: string[] | { name: string; backend?: string; supports_native_ui?: boolean }[]
}) {
  const store = useAgentStore()
  store.available = opts.available
  store.paired = opts.paired
  // Adaptamos string[] simple o objetos del test al shape AgentScanner del store.
  store.scanners = (opts.scanners ?? []).map((s) =>
    typeof s === 'string'
      ? { name: s, backend: 'sane', supports_native_ui: false }
      : { backend: 'sane', supports_native_ui: false, ...s },
  )
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

// ────────────────────────────────────────────────────────────────────────
// Sprint D, hito 13 — integración con ScannerOptionsDialog y app config.
//
// Sin app prop (back-compat): comportamiento previo intacto.
// Con app prop: 3 ramas según supports_native_ui del scanner y
// scan_show_dialog de la aplicación:
//   - native_ui=true                    → manda show_ui=true, sin dialog
//   - native_ui=false + show_dialog=t   → abre dialog, submit dispara con options
//   - native_ui=false + show_dialog=f   → directo, sin options ni show_ui
// ────────────────────────────────────────────────────────────────────────

describe('ScanFromAgentMenu — hito 13 (estrategia de UX)', () => {
  it('sin app prop: flatbed sigue llamando sin options ni show_ui (back-compat)', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanFlatbed).mockResolvedValueOnce({
      created: [{ id: 1, batch_id: 42, page_index: 0 }],
      batch_page_count: 1,
    })

    const wrapper = mount(ScanFromAgentMenu, { props: { batchId: 42 } })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    const call = vi.mocked(scanFlatbed).mock.calls[0][0]
    expect(call).toEqual({ scanner_name: 'dev:001', batch_id: 42 })
    expect(call.options).toBeUndefined()
    expect(call.show_ui).toBeUndefined()
    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(false)
  })

  it('supports_native_ui=true: flatbed manda show_ui=true sin abrir dialog', async () => {
    setStore({
      available: true,
      paired: true,
      scanners: [{ name: 'TWAIN: Canon', supports_native_ui: true, backend: 'twain' }],
    })
    vi.mocked(scanFlatbed).mockResolvedValueOnce({ created: [], batch_page_count: 0 })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    const call = vi.mocked(scanFlatbed).mock.calls[0][0]
    expect(call.show_ui).toBe(true)
    expect(call.options).toBeUndefined()
    // Native UI no abre el dialog dinámico.
    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(false)
  })

  it('supports_native_ui=true: ADF también manda show_ui=true', async () => {
    setStore({
      available: true,
      paired: true,
      scanners: [{ name: 'TWAIN: Canon', supports_native_ui: true, backend: 'twain' }],
    })
    vi.mocked(scanAdf).mockReturnValueOnce(
      (async function* () {
        yield { event: 'completed', total: 0 } as AdfStreamEvent
      })() as ReturnType<typeof scanAdf>,
    )

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    const call = vi.mocked(scanAdf).mock.calls[0][0]
    expect(call.show_ui).toBe(true)
  })

  it('!native_ui + show_dialog=true + flatbed: abre dialog (no escanea aún)', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(true)
    expect(scanFlatbed).not.toHaveBeenCalled()
  })

  it('!native_ui + show_dialog=true + ADF: abre dialog (no escanea aún)', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(true)
    expect(scanAdf).not.toHaveBeenCalled()
  })

  it('dialog submit en modo flatbed: dispara scanFlatbed con options', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanFlatbed).mockResolvedValueOnce({ created: [], batch_page_count: 0 })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="dialog-submit"]').trigger('click')
    await flushPromises()

    expect(scanFlatbed).toHaveBeenCalledTimes(1)
    const call = vi.mocked(scanFlatbed).mock.calls[0][0]
    expect(call.options).toEqual({ resolution: 600, mode: 'Gray' })
    expect(call.show_ui).toBeUndefined()
    // Dialog cerrado tras submit.
    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(false)
    expect(wrapper.emitted('uploaded')).toBeTruthy()
  })

  it('dialog submit en modo ADF: dispara scanAdf con options (no scanFlatbed)', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanAdf).mockReturnValueOnce(
      (async function* () {
        yield { event: 'completed', total: 0 } as AdfStreamEvent
      })() as ReturnType<typeof scanAdf>,
    )

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-adf"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="dialog-submit"]').trigger('click')
    await flushPromises()

    expect(scanAdf).toHaveBeenCalledTimes(1)
    expect(scanFlatbed).not.toHaveBeenCalled()
    const call = vi.mocked(scanAdf).mock.calls[0][0]
    expect(call.options).toEqual({ resolution: 600, mode: 'Gray' })
  })

  it('dialog cancel: no dispara escaneo, oculta dialog', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="dialog-cancel"]').trigger('click')
    await flushPromises()

    expect(scanFlatbed).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(false)
  })

  it('!native_ui + show_dialog=false: directo sin options ni show_ui ni dialog', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    vi.mocked(scanFlatbed).mockResolvedValueOnce({ created: [], batch_page_count: 0 })

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: false }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="dialog-stub"]').exists()).toBe(false)
    const call = vi.mocked(scanFlatbed).mock.calls[0][0]
    expect(call.options).toBeUndefined()
    expect(call.show_ui).toBeUndefined()
  })

  it('dialog recibe scan_defaults_json parseado como initialDefaults', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })

    const app = makeApp({
      scan_show_dialog: true,
      scan_defaults_json: JSON.stringify({ resolution: 150, mode: 'Color' }),
    })
    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: app },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    const stub = wrapper.find('[data-testid="dialog-stub"]')
    expect(stub.exists()).toBe(true)
    expect(stub.attributes('data-initial')).toBe(
      JSON.stringify({ resolution: 150, mode: 'Color' }),
    )
    expect(stub.attributes('data-can-save')).toBe('true')
    expect(stub.attributes('data-scanner')).toBe('dev:001')
  })

  it('save-defaults: PATCHea applications con scan_defaults_json serializado', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    mockUpdate.mockResolvedValueOnce({})

    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: makeApp({ scan_show_dialog: true }) },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="dialog-save-defaults"]').trigger('click')
    await flushPromises()

    expect(mockUpdate).toHaveBeenCalledTimes(1)
    expect(mockUpdate).toHaveBeenCalledWith(7, {
      scan_defaults_json: JSON.stringify({ resolution: 600, mode: 'Gray' }),
    })
  })

  it('initialDefaults vacío si scan_defaults_json malformado', async () => {
    setStore({ available: true, paired: true, scanners: ['dev:001'] })
    const app = makeApp({
      scan_show_dialog: true,
      scan_defaults_json: 'not valid json',
    })
    const wrapper = mount(ScanFromAgentMenu, {
      props: { batchId: 42, application: app },
    })
    await flushPromises()
    await wrapper.find('[data-testid="btn-flatbed"]').trigger('click')
    await flushPromises()

    const stub = wrapper.find('[data-testid="dialog-stub"]')
    expect(stub.attributes('data-initial')).toBe('{}')
  })
})
