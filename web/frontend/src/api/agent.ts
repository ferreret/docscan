// Helpers de captura desde el agente local (sprint cliente local web,
// hito 10). El agente vive en otro origen (http://127.0.0.1:47816) así
// que estas funciones usan ``fetch`` directo en vez del cliente del
// SaaS. CORS lo gestiona el middleware del agente.

const AGENT_BASE_URL = 'http://127.0.0.1:47816'

export type ScanMode = 'Color' | 'Gray' | 'Lineart'

export interface ScanFlatbedRequest {
  scanner_name: string
  batch_id: number
  resolution?: number
  mode?: ScanMode
}

export interface ScanFlatbedResponse {
  created: Array<{
    id: number
    batch_id: number
    page_index: number
  }>
  batch_page_count: number
}

// Eventos del stream NDJSON de /scan-adf-and-upload (hito 8 del agente).
// El backend usa una clave 'event' como discriminator.
export type AdfStreamEvent =
  | { event: 'started' }
  | {
      event: 'page_uploaded'
      page_index: number
      page_id: number
      batch_page_count: number
    }
  | { event: 'completed'; total: number }
  | {
      event: 'error'
      code: 'scan_error' | 'upload_error' | 'saas_unavailable' | 'encode_error'
      detail: string
      status_code?: number
    }

export interface ScanAdfRequest extends ScanFlatbedRequest {}

export type TransferLocalMode = 'extracted' | 'zip'

export interface TransferLocalRequest {
  batch_id: number
  destination: string
  mode?: TransferLocalMode
}

export interface TransferLocalResponse {
  batch_id: number
  mode: TransferLocalMode
  path: string
  files_count: number
  bytes: number
}

async function extractDetail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      return String((body as { detail: unknown }).detail)
    }
  } catch {
    /* ignore */
  }
  return `HTTP ${res.status}`
}

export async function scanFlatbed(
  req: ScanFlatbedRequest,
): Promise<ScanFlatbedResponse> {
  const res = await fetch(`${AGENT_BASE_URL}/scan-and-upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scanner_name: req.scanner_name,
      batch_id: req.batch_id,
      resolution: req.resolution ?? 300,
      mode: req.mode ?? 'Color',
    }),
  })
  if (!res.ok) {
    throw new Error(await extractDetail(res))
  }
  return (await res.json()) as ScanFlatbedResponse
}

export async function* scanAdf(
  req: ScanAdfRequest,
): AsyncGenerator<AdfStreamEvent> {
  const res = await fetch(`${AGENT_BASE_URL}/scan-adf-and-upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scanner_name: req.scanner_name,
      batch_id: req.batch_id,
      resolution: req.resolution ?? 300,
      mode: req.mode ?? 'Color',
    }),
  })

  // Errores antes del stream (401, 404, 503): cuerpo JSON con `detail`.
  if (!res.ok || !res.body) {
    throw new Error(await extractDetail(res))
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let nl: number
      while ((nl = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, nl).trim()
        buffer = buffer.slice(nl + 1)
        if (line) {
          yield JSON.parse(line) as AdfStreamEvent
        }
      }
    }
    // Última línea sin '\n' final (caso defensivo: el agente siempre
    // termina cada línea con '\n', pero si el TCP cierra antes podríamos
    // tener bytes pendientes).
    buffer += decoder.decode()
    const tail = buffer.trim()
    if (tail) {
      yield JSON.parse(tail) as AdfStreamEvent
    }
  } finally {
    reader.releaseLock()
  }
}

export async function transferBatchToLocal(
  req: TransferLocalRequest,
): Promise<TransferLocalResponse> {
  const res = await fetch(`${AGENT_BASE_URL}/transfer-batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      batch_id: req.batch_id,
      destination: req.destination,
      mode: req.mode ?? 'extracted',
    }),
  })
  if (!res.ok) {
    throw new Error(await extractDetail(res))
  }
  return (await res.json()) as TransferLocalResponse
}
