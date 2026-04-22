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

// Variables disponibles en eventos de transferencia (sin pipeline).
const TRANSFER_RESULT_VAR: ContextVariable = {
  name: 'result',
  summary: 'TransferResult: success, errors, output_path.',
  members: [
    { name: 'success', description: 'bool — True si la transferencia fue correcta.' },
    { name: 'errors', description: 'list[str] — Errores producidos durante la transferencia.' },
    { name: 'output_path', description: 'str — Ruta del fichero o directorio de salida.' },
  ],
}

const TRANSFER_PAGE_RESULT_VAR: ContextVariable = {
  name: 'result',
  summary: 'Info de la página transferida: output_path, success, error.',
  members: [
    { name: 'output_path', description: 'str — Ruta del fichero generado para esta página.' },
    { name: 'success', description: 'bool — True si la página se transfirió correctamente.' },
    { name: 'error', description: 'str | None — Mensaje de error si la página falló.' },
  ],
}

const TRANSFER_BASE_VARS = [...BASE_VARS, TRANSFER_RESULT_VAR]

const PAGE_VAR: ContextVariable = CONTEXT_VARIABLES.find((v) => v.name === 'page')!

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
  {
    name: 'on_transfer_validate',
    description: 'Se ejecuta antes de la transferencia. Retorna False para abortar.',
    signature: 'on_transfer_validate(app, batch, result)',
    template: `def on_transfer_validate(app, batch, result):
    """Se ejecuta antes de la transferencia.

    Retorna False para abortar la transferencia.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        result: TransferResult (success, errors, output_path)
    """
    return True
`,
    contextVariables: TRANSFER_BASE_VARS,
  },
  {
    name: 'on_transfer_advanced',
    description: 'Se ejecuta tras la transferencia con el resultado final.',
    signature: 'on_transfer_advanced(app, batch, result)',
    template: `def on_transfer_advanced(app, batch, result):
    """Se ejecuta tras la transferencia estándar con el resultado final.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        result: TransferResult (success, errors, output_path)
    """
    pass
`,
    contextVariables: TRANSFER_BASE_VARS,
  },
  {
    name: 'on_transfer_page',
    description: 'Se ejecuta una vez por cada página transferida.',
    signature: 'on_transfer_page(app, batch, page, result)',
    template: `def on_transfer_page(app, batch, page, result):
    """Se ejecuta una vez por cada página transferida.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        page: PageContext (image, barcodes, ocr_text, fields, flags)
        result: info de la página transferida (output_path, success, error)
    """
    pass
`,
    contextVariables: [...BASE_VARS, PAGE_VAR, TRANSFER_PAGE_RESULT_VAR],
  },
]
