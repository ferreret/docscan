import { CONTEXT_VARIABLES, type ContextVariable } from './script-context-help'

export interface EventDefinition {
  name: string
  description: string
  signature: string
  template: string
  contextVariables: ContextVariable[]
}

// Reutiliza el catálogo de ScriptStep excluyendo `page` y `pipeline`
// (no disponibles en lifecycle events de nivel batch).
const BASE_VARS: ContextVariable[] = CONTEXT_VARIABLES.filter(
  (v) => v.name !== 'page' && v.name !== 'pipeline',
)

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
