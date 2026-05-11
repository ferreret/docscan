import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useScannerOptions, _resetScannerOptionsCache } from '@/composables/useScannerOptions'
import type { ScannerOptionsResponse } from '@/api/types'

const RESPONSE_SANE: ScannerOptionsResponse = {
  scanner: 'epson:fake',
  options: [
    {
      name: 'resolution',
      title: 'Resolución',
      description: 'DPI',
      type: 'int',
      unit: 'dpi',
      constraint: [75, 150, 300, 600],
      value: 300,
      is_active: true,
      is_settable: true,
    },
    {
      name: 'mode',
      title: 'Modo',
      description: 'Color/Gris/BW',
      type: 'string',
      unit: '',
      constraint: ['Color', 'Gray', 'Lineart'],
      value: 'Color',
      is_active: true,
      is_settable: true,
    },
  ],
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

describe('useScannerOptions', () => {
  beforeEach(() => {
    _resetScannerOptionsCache()
    vi.clearAllMocks()
  })

  it('fetch carga options del agente y las expone', async () => {
    const fetchMock = mockFetchOnce(RESPONSE_SANE)
    const opts = useScannerOptions()

    await opts.fetch('epson:fake')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/127\.0\.0\.1:47816\/scanners\/epson:fake\/options$/)
    expect(opts.options.value).toHaveLength(2)
    expect(opts.options.value[0].name).toBe('resolution')
    expect(opts.error.value).toBeNull()
    expect(opts.loading.value).toBe(false)
  })

  it('fetch escapa nombres con caracteres especiales pero respeta : y /', async () => {
    // SANE devuelve nombres como "plustek:libusb:001:003" que llevan ':'.
    // El backend usa path converter :path, así que '/' también pasa intacto.
    // Sólo escapamos caracteres reservados de query strings y espacios.
    const fetchMock = mockFetchOnce({ scanner: 'plustek:libusb:001:003', options: [] })
    const opts = useScannerOptions()

    await opts.fetch('plustek:libusb:001:003')

    const url = fetchMock.mock.calls[0][0] as string
    // No queremos %3A reemplazando los ':' (rompe el path converter SANE)
    expect(url).toContain('plustek:libusb:001:003')
    expect(url).not.toContain('%3A')
  })

  it('fetch propaga errores 4xx/5xx en error', async () => {
    mockFetchOnce({ detail: 'Escáner no encontrado' }, false, 404)
    const opts = useScannerOptions()

    await opts.fetch('inexistente')

    expect(opts.options.value).toEqual([])
    expect(opts.error.value).toContain('no encontrado')
    expect(opts.loading.value).toBe(false)
  })

  it('fetch trata error de red como agente caído', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch'))
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
    const opts = useScannerOptions()

    await opts.fetch('epson:fake')

    expect(opts.options.value).toEqual([])
    expect(opts.error.value).toContain('Failed to fetch')
  })

  it('fetch loading=true durante la petición y false al acabar', async () => {
    let resolveFetch: (v: unknown) => void = () => {}
    const promise = new Promise((resolve) => { resolveFetch = resolve })
    globalThis.fetch = vi.fn().mockReturnValueOnce(promise) as unknown as typeof globalThis.fetch
    const opts = useScannerOptions()

    const fetchPromise = opts.fetch('epson:fake')
    expect(opts.loading.value).toBe(true)

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => RESPONSE_SANE,
      text: async () => JSON.stringify(RESPONSE_SANE),
    })
    await fetchPromise

    expect(opts.loading.value).toBe(false)
  })

  it('cache: segunda llamada al mismo scanner no re-pega al agente', async () => {
    const fetchMock = mockFetchOnce(RESPONSE_SANE)
    const opts = useScannerOptions()
    await opts.fetch('epson:fake')

    // Segundo composable independiente — el cache es de módulo.
    const opts2 = useScannerOptions()
    await opts2.fetch('epson:fake')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(opts2.options.value).toHaveLength(2)
  })

  it('cache: scanner distinto sí re-pega al agente', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => RESPONSE_SANE,
        text: async () => JSON.stringify(RESPONSE_SANE),
      })
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => ({ scanner: 'otro', options: [] }),
        text: async () => JSON.stringify({ scanner: 'otro', options: [] }),
      })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const opts = useScannerOptions()
    await opts.fetch('epson:fake')
    await opts.fetch('otro')

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('refresh:true invalida cache y pasa ?refresh=true al agente', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => RESPONSE_SANE,
        text: async () => JSON.stringify(RESPONSE_SANE),
      })
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => RESPONSE_SANE,
        text: async () => JSON.stringify(RESPONSE_SANE),
      })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
    const opts = useScannerOptions()

    await opts.fetch('epson:fake')
    await opts.fetch('epson:fake', { refresh: true })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const secondUrl = fetchMock.mock.calls[1][0] as string
    expect(secondUrl).toContain('?refresh=true')
  })

  it('error en refresh deja cache previo intacto y se puede recuperar', async () => {
    // 1) Carga OK → cache poblado
    // 2) refresh falla → error.value poblado, cache previo sigue válido
    // 3) fetch sin refresh devuelve cache (no re-pega)
    // 4) fetch con refresh vuelve a pegar y limpia el error
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => RESPONSE_SANE,
        text: async () => JSON.stringify(RESPONSE_SANE),
      })
      .mockResolvedValueOnce({
        ok: false, status: 503,
        json: async () => ({ detail: 'busy' }),
        text: async () => JSON.stringify({ detail: 'busy' }),
      })
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => RESPONSE_SANE,
        text: async () => JSON.stringify(RESPONSE_SANE),
      })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
    const opts = useScannerOptions()

    await opts.fetch('epson:fake')
    await opts.fetch('epson:fake', { refresh: true })
    expect(opts.error.value).toContain('busy')

    // Sin refresh: devuelve cache previo, no toca al backend.
    await opts.fetch('epson:fake')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(opts.options.value).toHaveLength(2)

    // Con refresh: re-pega y se recupera.
    await opts.fetch('epson:fake', { refresh: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(opts.error.value).toBeNull()
    expect(opts.options.value).toHaveLength(2)
  })
})
