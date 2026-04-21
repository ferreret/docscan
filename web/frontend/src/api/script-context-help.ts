// Catálogo estático consumido por el editor de ScriptStep:
//   - CONTEXT_VARIABLES → panel lateral + autocompletado
//   - SNIPPETS          → menú "Insertar snippet"
//   - DEFAULT_SCRIPT_TEMPLATE → defaultsFor('script') en el store

export interface ContextMember {
  name: string
  signature?: string
  description: string
}

export interface ContextVariable {
  name: string
  summary: string
  members?: ContextMember[]
}

export const CONTEXT_VARIABLES: ContextVariable[] = [
  { name: 'app', summary: 'AppContext: id, name.' },
  { name: 'batch', summary: 'BatchContext: id, state, fields, page_count.' },
  {
    name: 'page',
    summary: 'PageContext: imagen y datos extraídos.',
    members: [
      { name: 'image', description: 'np.ndarray BGR.' },
      { name: 'barcodes', description: 'list[Barcode] con .value, .symbology.' },
      { name: 'ocr_text', description: 'str — OCR acumulado.' },
      { name: 'fields', description: 'dict[str, Any] — metadatos de la página.' },
      { name: 'flags', description: 'dict[str, Any] — banderas internas.' },
    ],
  },
  {
    name: 'pipeline',
    summary: 'Control de flujo del pipeline (solo ScriptStep).',
    members: [
      { name: 'skip_step', signature: 'skip_step(step_id)', description: 'Marca un paso por id para saltarlo.' },
      { name: 'skip_to', signature: 'skip_to(step_id)', description: 'Salta hasta el step con ese id.' },
      { name: 'abort', signature: 'abort(reason="")', description: 'Interrumpe el pipeline para esta página.' },
      { name: 'repeat_step', signature: 'repeat_step(step_id)', description: 'Re-ejecuta un paso por id (max 3).' },
      { name: 'replace_image', signature: 'replace_image(img)', description: 'Sustituye page.image.' },
      { name: 'get_metadata', signature: 'get_metadata(key)', description: 'Lee metadata del pipeline.' },
      { name: 'set_metadata', signature: 'set_metadata(k, v)', description: 'Escribe metadata del pipeline.' },
    ],
  },
  { name: 'log', summary: 'logger estándar: log.info(...), log.warning(...).' },
  { name: 'http', summary: 'httpx — http.get(url), http.post(url, json=...).' },
  { name: 're', summary: 'módulo re de Python.' },
  { name: 'json', summary: 'módulo json de Python.' },
  { name: 'datetime', summary: 'módulo datetime de Python.' },
  { name: 'Path', summary: 'pathlib.Path.' },
]

export interface Snippet {
  id: string
  label: string
  description: string
  code: string
}

export const SNIPPETS: Snippet[] = [
  {
    id: 'barcode-to-field',
    label: 'Asignar primer barcode a page.fields',
    description: 'Copia el valor del primer barcode detectado a page.fields["documento"].',
    code: 'if page.barcodes:\n    page.fields["documento"] = page.barcodes[0].value\n',
  },
  {
    id: 'ocr-to-field',
    label: 'Extraer campo con regex del OCR',
    description: 'Busca un patrón en page.ocr_text y lo guarda en page.fields.',
    code: 'm = re.search(r"NIF:\\s*([A-Z0-9]+)", page.ocr_text or "")\nif m:\n    page.fields["nif"] = m.group(1)\n',
  },
  {
    id: 'http-download',
    label: 'Consultar API externa',
    description: 'Envía el valor de un campo a una API y guarda la respuesta.',
    code: 'doc = page.fields.get("documento")\nif doc:\n    r = http.get(f"https://api.example.com/docs/{doc}")\n    if r.status_code == 200:\n        page.fields["doc_data"] = r.json()\n',
  },
  {
    id: 'abort-if-no-barcodes',
    label: 'Abortar si no hay barcodes',
    description: 'Interrumpe la página si el barcode step no detectó nada.',
    code: 'if not page.barcodes:\n    pipeline.abort(reason="sin barcodes")\n',
  },
]

export const DEFAULT_SCRIPT_TEMPLATE = `def process(app, batch, page, pipeline):
    """Procesa cada página del pipeline.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        page: PageContext (image, barcodes, ocr_text, fields, flags)
        pipeline: PipelineContext (skip_step, abort, repeat_step, metadata)
    """
    pass
`
