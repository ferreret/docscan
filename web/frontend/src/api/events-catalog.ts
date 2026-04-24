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

const BASE_WITH_PAGE_VARS: ContextVariable[] = [...BASE_VARS, PAGE_VAR]

const KEY_VAR: ContextVariable = {
  name: 'key',
  summary: 'str — Tecla pulsada en formato "Ctrl+Alt+L" o similar.',
  members: [],
}

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
  {
    name: 'on_batch_loaded',
    description: 'Se dispara al abrir el lote en el workbench. Retornar {cancel: true} impide la carga.',
    signature: 'def on_batch_loaded(app, batch)',
    template:
      'def on_batch_loaded(app, batch):\n' +
      '    """Se ejecuta al abrir el lote."""\n' +
      '    pass\n',
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_prev',
    description: 'Antes de navegar a la página anterior. Retornar {cancel: true} o {target_page_id: N}.',
    signature: 'def on_navigate_prev(app, batch, page)',
    template:
      'def on_navigate_prev(app, batch, page):\n' +
      '    """Controla la navegación previa."""\n' +
      '    return None\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_navigate_next',
    description: 'Antes de navegar a la página siguiente. Retornar {cancel: true} o {target_page_id: N}.',
    signature: 'def on_navigate_next(app, batch, page)',
    template:
      'def on_navigate_next(app, batch, page):\n' +
      '    """Controla la navegación siguiente."""\n' +
      '    return None\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_page_changed',
    description: 'Tras cambiar a una página. Fire-and-forget. Puede mutar page.fields para actualizar la UI.',
    signature: 'def on_page_changed(app, batch, page)',
    template:
      'def on_page_changed(app, batch, page):\n' +
      '    """Al navegar a otra página."""\n' +
      '    pass\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_key_event',
    description: 'Tecla pulsada no mapeada por defecto. Fire-and-forget.',
    signature: 'def on_key_event(app, batch, key)',
    template:
      'def on_key_event(app, batch, key):\n' +
      '    """Maneja teclas custom."""\n' +
      '    pass\n',
    contextVariables: [...BASE_VARS, KEY_VAR],
  },
]
