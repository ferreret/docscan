import type { ContextVariable } from './script-context-help'

export interface EventDefinition {
  name: string
  description: string
  signature: string
  template: string
  contextVariables: ContextVariable[]
}

const BASE_VARS: ContextVariable[] = [
  { name: 'app',      summary: 'AppContext: id, name.' },
  { name: 'batch',    summary: 'BatchContext: id, state, fields, page_count.' },
  { name: 'log',      summary: 'logger estándar: log.info(...), log.warning(...).' },
  { name: 'http',     summary: 'httpx — http.get(url), http.post(url, json=...).' },
  { name: 're',       summary: 'módulo re de Python.' },
  { name: 'json',     summary: 'módulo json de Python.' },
  { name: 'datetime', summary: 'módulo datetime de Python.' },
  { name: 'Path',     summary: 'pathlib.Path.' },
]

export const EVENT_DEFINITIONS: EventDefinition[] = [
  {
    name: 'on_scan_complete',
    description: 'Al terminar el pipeline sobre todas las páginas del lote.',
    signature: 'on_scan_complete(app, batch)',
    template: `def on_scan_complete(app, batch):
    """Se ejecuta una vez al finalizar el pipeline para todas las páginas del lote."""
    pass
`,
    contextVariables: BASE_VARS,
  },
]
