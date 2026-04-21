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

const PAGE_VAR: ContextVariable = {
  name: 'page',
  summary: 'PageContext: imagen y datos extraídos.',
  members: [
    { name: 'image',    description: 'np.ndarray BGR.' },
    { name: 'barcodes', description: 'list[Barcode] con .value, .symbology.' },
    { name: 'ocr_text', description: 'str — OCR acumulado.' },
    { name: 'fields',   description: 'dict[str, Any] — metadatos de la página.' },
    { name: 'flags',    description: 'dict[str, Any] — banderas internas.' },
  ],
}

const RESULT_VAR: ContextVariable = {
  name: 'result',
  summary: 'TransferResult: destino, status, detalles de la transferencia.',
}

const KEY_VAR: ContextVariable = {
  name: 'key',
  summary: 'str — nombre de la tecla pulsada (ej. "F2", "Ctrl+S").',
}

const VERIFICATION_PANEL_VARS: ContextVariable[] = [
  {
    name: 'self.api',
    summary: 'API del panel de verificación (acceso a lote/páginas).',
    members: [
      { name: 'get_page_image',    signature: 'get_page_image(index)',       description: 'Devuelve la imagen np.ndarray de la página.' },
      { name: 'get_page_barcodes', signature: 'get_page_barcodes(index)',    description: 'Lista de barcodes de la página.' },
      { name: 'get_page_ocr_text', signature: 'get_page_ocr_text(index)',    description: 'Texto OCR de la página.' },
      { name: 'get_page_fields',   signature: 'get_page_fields(index)',      description: 'Dict de fields de la página.' },
      { name: 'set_page_field',    signature: 'set_page_field(name, value)', description: 'Actualiza un field de la página actual.' },
      { name: 'get_batch_fields',  signature: 'get_batch_fields()',          description: 'Dict de fields del lote.' },
      { name: 'set_batch_field',   signature: 'set_batch_field(name, value)', description: 'Actualiza un field del lote.' },
      { name: 'navigate_to',       signature: 'navigate_to(index)',          description: 'Navega a la página indicada.' },
      { name: 'log',               signature: 'log(msg)',                    description: 'Loguea un mensaje.' },
    ],
  },
]

function tpl(name: string, args: string, docstring: string): string {
  return `def ${name}(${args}):
    """${docstring}"""
    pass
`
}

export const EVENT_DEFINITIONS: EventDefinition[] = [
  {
    name: 'on_app_start',
    description: 'Al abrir la aplicación.',
    signature: 'on_app_start(app, batch)',
    template: tpl('on_app_start', 'app, batch', 'Se ejecuta al abrir la aplicación en el Workbench.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_app_end',
    description: 'Al cerrar la aplicación.',
    signature: 'on_app_end(app, batch)',
    template: tpl('on_app_end', 'app, batch', 'Se ejecuta al cerrar la aplicación.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_import',
    description: 'Al pulsar Procesar. Reemplaza la carga estándar si está definido.',
    signature: 'on_import(app, batch)',
    template: tpl('on_import', 'app, batch', 'Reemplaza la lógica de importación estándar cuando está definido.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_scan_complete',
    description: 'Al terminar el pipeline sobre todas las páginas del lote.',
    signature: 'on_scan_complete(app, batch)',
    template: tpl('on_scan_complete', 'app, batch', 'Se ejecuta una vez al finalizar el pipeline para todas las páginas.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_transfer_validate',
    description: 'Antes de transferir; retornar False cancela.',
    signature: 'on_transfer_validate(app, batch) -> bool',
    template: `def on_transfer_validate(app, batch):
    """Se ejecuta antes de transferir. Devolver False cancela la transferencia."""
    return True
`,
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_transfer_advanced',
    description: 'Transferencia scripteada (reemplaza la transferencia simple).',
    signature: 'on_transfer_advanced(app, batch, result)',
    template: tpl('on_transfer_advanced', 'app, batch, result', 'Reemplaza la transferencia simple con lógica personalizada.'),
    contextVariables: [...BASE_VARS, RESULT_VAR],
  },
  {
    name: 'on_transfer_page',
    description: 'Post-copia por página durante la transferencia simple.',
    signature: 'on_transfer_page(app, batch, page, result)',
    template: tpl('on_transfer_page', 'app, batch, page, result', 'Se ejecuta tras copiar cada página en la transferencia simple.'),
    contextVariables: [...BASE_VARS, PAGE_VAR, RESULT_VAR],
  },
  {
    name: 'on_navigate_prev',
    description: 'Navegación previa programable.',
    signature: 'on_navigate_prev(app, batch)',
    template: tpl('on_navigate_prev', 'app, batch', 'Handler personalizado de navegación anterior.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_next',
    description: 'Navegación siguiente programable.',
    signature: 'on_navigate_next(app, batch)',
    template: tpl('on_navigate_next', 'app, batch', 'Handler personalizado de navegación siguiente.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_script',
    description: 'Botón de navegación programable del visor.',
    signature: 'on_navigate_script(app, batch)',
    template: tpl('on_navigate_script', 'app, batch', 'Handler personalizado del botón de navegación del visor.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_key_event',
    description: 'Tecla personalizada.',
    signature: 'on_key_event(app, batch, key)',
    template: tpl('on_key_event', 'app, batch, key', 'Handler personalizado de eventos de teclado. key es un string con el nombre de la tecla.'),
    contextVariables: [...BASE_VARS, KEY_VAR],
  },
  {
    name: 'init_global',
    description: 'Al iniciar el programa (script global del launcher).',
    signature: 'init_global(app, batch)',
    template: tpl('init_global', 'app, batch', 'Se ejecuta al iniciar el programa (nivel launcher).'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'verification_panel',
    description: 'Panel de verificación (clase VerificationPanel).',
    signature: 'class MyVerificationPanel(VerificationPanel)',
    template: `class MyVerificationPanel(VerificationPanel):
    """Panel de verificación personalizado.

    Métodos sobreescribibles: setup_ui(), on_page_changed(index),
    on_pipeline_completed(index), on_batch_loaded(),
    validate_page(index) -> (bool, str), validate() -> (bool, str), cleanup().
    """

    def setup_ui(self):
        pass
`,
    contextVariables: VERIFICATION_PANEL_VARS,
  },
]
