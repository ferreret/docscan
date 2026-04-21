import { describe, it, expect } from 'vitest'
import {
  CONTEXT_VARIABLES,
  SNIPPETS,
  DEFAULT_SCRIPT_TEMPLATE,
} from '@/api/script-context-help'

describe('script-context-help', () => {
  it('CONTEXT_VARIABLES incluye todas las variables inyectadas', () => {
    const names = CONTEXT_VARIABLES.map((v) => v.name)
    const expected = [
      'app', 'batch', 'page', 'pipeline',
      'log', 'http', 're', 'json', 'datetime', 'Path',
    ]
    for (const name of expected) {
      expect(names).toContain(name)
    }
    // page y pipeline deben exponer members
    const page = CONTEXT_VARIABLES.find((v) => v.name === 'page')!
    expect(page.members?.map((m) => m.name)).toEqual(
      expect.arrayContaining(['image', 'barcodes', 'ocr_text', 'fields', 'flags']),
    )
    const pipeline = CONTEXT_VARIABLES.find((v) => v.name === 'pipeline')!
    expect(pipeline.members?.map((m) => m.name)).toEqual(
      expect.arrayContaining([
        'skip_step', 'skip_to', 'abort', 'repeat_step',
        'replace_image', 'get_metadata', 'set_metadata',
      ]),
    )
  })

  it('SNIPPETS tiene 4 entradas con id único', () => {
    expect(SNIPPETS).toHaveLength(4)
    const ids = SNIPPETS.map((s) => s.id)
    expect(new Set(ids).size).toBe(4)
    for (const snippet of SNIPPETS) {
      expect(snippet.label).toBeTruthy()
      expect(snippet.code).toBeTruthy()
    }
  })

  it('DEFAULT_SCRIPT_TEMPLATE empieza con la firma process(...)', () => {
    expect(DEFAULT_SCRIPT_TEMPLATE.startsWith(
      'def process(app, batch, page, pipeline):',
    )).toBe(true)
  })
})
