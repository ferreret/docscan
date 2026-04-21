import { describe, it, expect } from 'vitest'
import {
  shouldPrefixNewline,
  buildContextSuggestions,
} from '@/components/pipeline/forms/script-editor/editor'

describe('script-editor/editor — funciones puras', () => {
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
      const out = buildContextSuggestions('')
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'app', 'batch', 'page', 'pipeline', 'log', 'http', 're', 'json', 'datetime', 'Path',
      ]))
    })

    it('para prefijo "page." devuelve los members de page', () => {
      const out = buildContextSuggestions('page.')
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'image', 'barcodes', 'ocr_text', 'fields', 'flags',
      ]))
    })
  })
})
