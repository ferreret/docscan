import { describe, it, expect } from 'vitest'
import {
  shouldPrefixNewline,
  buildContextSuggestions,
} from '@/components/code-editor/editor'
import type { ContextVariable } from '@/api/script-context-help'

const SAMPLE_VARS: ContextVariable[] = [
  { name: 'app', summary: 'AppContext.' },
  { name: 'batch', summary: 'BatchContext.' },
  {
    name: 'page',
    summary: 'PageContext.',
    members: [
      { name: 'image', description: 'np.ndarray.' },
      { name: 'barcodes', description: 'lista.' },
      { name: 'ocr_text', description: 'str.' },
      { name: 'fields', description: 'dict.' },
      { name: 'flags', description: 'dict.' },
    ],
  },
  {
    name: 'self.api',
    summary: 'API de verification panel.',
    members: [
      { name: 'get_page_image', signature: 'get_page_image(index)', description: 'Imagen.' },
      { name: 'navigate_to', signature: 'navigate_to(index)', description: 'Navega.' },
    ],
  },
  { name: 'log', summary: 'logger.' },
]

describe('code-editor/editor — funciones puras', () => {
  describe('shouldPrefixNewline', () => {
    it('devuelve false si la línea actual está vacía', () => {
      expect(shouldPrefixNewline('')).toBe(false)
    })

    it('devuelve false si la línea solo tiene whitespace (indentación)', () => {
      expect(shouldPrefixNewline('    ')).toBe(false)
    })

    it('devuelve true si la línea tiene contenido', () => {
      expect(shouldPrefixNewline('x = 1')).toBe(true)
    })
  })

  describe('buildContextSuggestions', () => {
    it('para prefijo vacío devuelve todas las variables top-level', () => {
      const out = buildContextSuggestions('', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'app', 'batch', 'page', 'self.api', 'log',
      ]))
    })

    it('para prefijo "page." devuelve los members de page', () => {
      const out = buildContextSuggestions('page.', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'image', 'barcodes', 'ocr_text', 'fields', 'flags',
      ]))
    })

    it('para prefijo multi-nivel "self.api." devuelve los members de self.api', () => {
      const out = buildContextSuggestions('self.api.', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'get_page_image', 'navigate_to',
      ]))
    })

    it('para lista vacía de vars devuelve []', () => {
      expect(buildContextSuggestions('', [])).toEqual([])
      expect(buildContextSuggestions('page.', [])).toEqual([])
    })
  })
})
