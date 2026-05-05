import { describe, it, expect, beforeEach } from 'vitest'
import { useOverlayToggles } from '@/composables/useOverlayToggles'

describe('useOverlayToggles', () => {
  beforeEach(() => { localStorage.clear() })

  it('defaults: both true', () => {
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(true)
    expect(t.showFields.value).toBe(true)
  })

  it('persists to localStorage on change', async () => {
    const t = useOverlayToggles()
    t.showBarcodes.value = false
    // watch es async, esperar al siguiente tick
    await new Promise(resolve => setTimeout(resolve, 0))
    const stored = JSON.parse(localStorage.getItem('workbench.overlays')!)
    expect(stored.barcodes).toBe(false)
  })

  it('loads from localStorage on init', () => {
    localStorage.setItem(
      'workbench.overlays',
      JSON.stringify({ barcodes: false, fields: true }),
    )
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(false)
    expect(t.showFields.value).toBe(true)
  })

  it('handles corrupt localStorage gracefully', () => {
    localStorage.setItem('workbench.overlays', 'not json')
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(true)
    expect(t.showFields.value).toBe(true)
  })

  it('handles partial localStorage data', () => {
    localStorage.setItem('workbench.overlays', JSON.stringify({ barcodes: false }))
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(false)
    expect(t.showFields.value).toBe(true)  // default
  })
})
