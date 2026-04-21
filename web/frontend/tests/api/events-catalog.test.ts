import { describe, it, expect } from 'vitest'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

const EXPECTED_NAMES = [
  'on_app_start',
  'on_app_end',
  'on_import',
  'on_scan_complete',
  'on_transfer_validate',
  'on_transfer_advanced',
  'on_transfer_page',
  'on_navigate_prev',
  'on_navigate_next',
  'on_navigate_script',
  'on_key_event',
  'init_global',
  'verification_panel',
]

describe('events-catalog', () => {
  it('EVENT_DEFINITIONS tiene 13 entradas con nombres únicos que coinciden con el desktop', () => {
    expect(EVENT_DEFINITIONS).toHaveLength(13)
    const names = EVENT_DEFINITIONS.map((e) => e.name)
    expect(new Set(names).size).toBe(13)
    for (const n of EXPECTED_NAMES) {
      expect(names).toContain(n)
    }
  })

  it('cada template empieza con la firma correcta (def o class)', () => {
    for (const event of EVENT_DEFINITIONS) {
      if (event.name === 'verification_panel') {
        expect(event.template.startsWith('class ')).toBe(true)
      } else {
        expect(event.template.startsWith(`def ${event.name}(`)).toBe(true)
      }
    }
  })

  it('verification_panel expone self.api con ≥9 miembros', () => {
    const vp = EVENT_DEFINITIONS.find((e) => e.name === 'verification_panel')!
    const selfApi = vp.contextVariables.find((v) => v.name === 'self.api')
    expect(selfApi).toBeDefined()
    expect(selfApi!.members?.length ?? 0).toBeGreaterThanOrEqual(9)
    const memberNames = selfApi!.members!.map((m) => m.name)
    expect(memberNames).toEqual(expect.arrayContaining([
      'get_page_image', 'get_page_barcodes', 'navigate_to', 'log',
    ]))
  })
})
