import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  scanFlatbed,
  scanAdf,
  type AdfStreamEvent,
} from '@/api/agent'

beforeEach(() => {
  vi.restoreAllMocks()
})

// ----------------------------------------------------------------------
// helpers
// ----------------------------------------------------------------------

function ndjsonStream(lines: object[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const obj of lines) {
        controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'))
      }
      controller.close()
    },
  })
}

function chunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
}

// ----------------------------------------------------------------------
// scanFlatbed
// ----------------------------------------------------------------------

describe('scanFlatbed', () => {
  it('POST /scan-and-upload con scanner_name + batch_id + defaults', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        created: [{ id: 100, batch_id: 42, page_index: 0 }],
        batch_page_count: 1,
      }),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const result = await scanFlatbed({
      scanner_name: 'dev:001',
      batch_id: 42,
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/127\.0\.0\.1:47816\/scan-and-upload$/)
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(body.scanner_name).toBe('dev:001')
    expect(body.batch_id).toBe(42)
    // Defaults razonables
    expect(body.resolution).toBe(300)
    expect(body.mode).toBe('Color')
    expect(result.batch_page_count).toBe(1)
  })

  it('respeta resolution y mode si se pasan', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ created: [], batch_page_count: 0 }),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    await scanFlatbed({
      scanner_name: 'dev:001',
      batch_id: 42,
      resolution: 600,
      mode: 'Gray',
    })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body.resolution).toBe(600)
    expect(body.mode).toBe('Gray')
  })

  it('lanza error con detail si el agente devuelve 4xx', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Escáner no existe: 'no-such'" }),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    await expect(
      scanFlatbed({ scanner_name: 'no-such', batch_id: 42 }),
    ).rejects.toThrow(/no existe/i)
  })
})

// ----------------------------------------------------------------------
// scanAdf
// ----------------------------------------------------------------------

describe('scanAdf', () => {
  it('parsea NDJSON línea a línea y emite eventos en orden', async () => {
    const events = [
      { event: 'started' },
      { event: 'page_uploaded', page_index: 0, page_id: 100, batch_page_count: 1 },
      { event: 'page_uploaded', page_index: 1, page_id: 101, batch_page_count: 2 },
      { event: 'completed', total: 2 },
    ]
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/x-ndjson' }),
      body: ndjsonStream(events),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const collected: AdfStreamEvent[] = []
    for await (const ev of scanAdf({ scanner_name: 'dev:001', batch_id: 42 })) {
      collected.push(ev)
    }

    expect(collected).toEqual(events)
  })

  it('parsea correctamente cuando un chunk parte una línea', async () => {
    // El servidor mete 2 eventos pero el TCP los entrega en 3 chunks que
    // cortan en mitad de la línea. El parser debe acumular en buffer.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: chunkedStream([
        '{"event":"started"}\n{"event":"page_upload',
        'ed","page_index":0,"page_id":100,',
        '"batch_page_count":1}\n{"event":"completed","total":1}\n',
      ]),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const collected: AdfStreamEvent[] = []
    for await (const ev of scanAdf({ scanner_name: 'dev:001', batch_id: 42 })) {
      collected.push(ev)
    }

    expect(collected.map((e) => e.event)).toEqual([
      'started',
      'page_uploaded',
      'completed',
    ])
    expect(collected[1]).toMatchObject({ page_index: 0, page_id: 100 })
  })

  it('emite la última línea aunque no termine en \\n', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: chunkedStream(['{"event":"started"}\n{"event":"completed","total":0}']),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const collected: AdfStreamEvent[] = []
    for await (const ev of scanAdf({ scanner_name: 'dev:001', batch_id: 42 })) {
      collected.push(ev)
    }

    expect(collected).toHaveLength(2)
    expect(collected[1].event).toBe('completed')
  })

  it('lanza error si el agente devuelve 4xx antes del stream', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Escáner no existe: 'no-such'" }),
      body: null,
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const gen = scanAdf({ scanner_name: 'no-such', batch_id: 42 })
    await expect(gen.next()).rejects.toThrow(/no existe/i)
  })

  it('emite el evento "error" del stream sin lanzar excepción', async () => {
    // Cuando algo falla a media iteración el agente emite una línea
    // {event:"error", code, detail} y cierra el stream con HTTP 200. El
    // parser debe entregarla como un evento más; el componente decide qué
    // hacer con ella.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: ndjsonStream([
        { event: 'started' },
        { event: 'page_uploaded', page_index: 0, page_id: 100, batch_page_count: 1 },
        { event: 'error', code: 'scan_error', detail: 'paper jam' },
      ]),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const collected: AdfStreamEvent[] = []
    for await (const ev of scanAdf({ scanner_name: 'dev:001', batch_id: 42 })) {
      collected.push(ev)
    }

    expect(collected[2]).toMatchObject({
      event: 'error',
      code: 'scan_error',
      detail: 'paper jam',
    })
  })

  it('respeta resolution y mode si se pasan', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: ndjsonStream([{ event: 'started' }, { event: 'completed', total: 0 }]),
    })
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const gen = scanAdf({
      scanner_name: 'dev:001',
      batch_id: 42,
      resolution: 600,
      mode: 'Gray',
    })
    // consumir
    while (!(await gen.next()).done) {}

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body.resolution).toBe(600)
    expect(body.mode).toBe('Gray')
  })
})
