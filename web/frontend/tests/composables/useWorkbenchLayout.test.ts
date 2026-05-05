import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchLayout, _resetLayoutForTests } from '@/composables/useWorkbenchLayout'

describe('useWorkbenchLayout', () => {
  beforeEach(() => {
    localStorage.clear()
    _resetLayoutForTests()
  })

  it('returns default sizes when localStorage is empty', () => {
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [10, 65, 25], rightVertical: [50, 50] })
  })

  it('loads valid sizes from localStorage', () => {
    localStorage.setItem('workbench.layout', JSON.stringify({ columns: [20, 50, 30], rightVertical: [60, 40] }))
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value.columns).toEqual([20, 50, 30])
    expect(sizes.value.rightVertical).toEqual([60, 40])
  })

  it('falls back to defaults when localStorage value is malformed', () => {
    localStorage.setItem('workbench.layout', '{not json')
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [10, 65, 25], rightVertical: [50, 50] })
  })

  it('falls back to defaults when shape is wrong', () => {
    localStorage.setItem('workbench.layout', JSON.stringify({ columns: [50, 50] })) // only 2 cols
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [10, 65, 25], rightVertical: [50, 50] })
  })

  it('setSizes updates ref and persists to localStorage', () => {
    const { setSizes, sizes } = useWorkbenchLayout()
    setSizes({ columns: [10, 60, 30], rightVertical: [40, 60] })
    expect(sizes.value.columns).toEqual([10, 60, 30])
    expect(JSON.parse(localStorage.getItem('workbench.layout')!)).toEqual({
      columns: [10, 60, 30], rightVertical: [40, 60],
    })
  })
})
