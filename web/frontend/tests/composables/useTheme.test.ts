import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTheme, _resetThemeForTests } from '@/composables/useTheme'

function setMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    setMatchMedia(false)
    _resetThemeForTests()
  })

  it('defaults to "auto" when localStorage is empty', () => {
    const { preference } = useTheme()
    expect(preference.value).toBe('auto')
  })

  it('loads valid preference from localStorage', () => {
    localStorage.setItem('theme', 'dark')
    _resetThemeForTests()
    const { preference } = useTheme()
    expect(preference.value).toBe('dark')
  })

  it('sanitizes invalid localStorage value to "auto"', () => {
    localStorage.setItem('theme', 'pink')
    _resetThemeForTests()
    const { preference } = useTheme()
    expect(preference.value).toBe('auto')
  })

  it('setPreference updates ref, localStorage and html data-theme', () => {
    const { setPreference, preference } = useTheme()
    setPreference('dark')
    expect(preference.value).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('current reflects OS when preference is "auto"', () => {
    setMatchMedia(true) // OS prefers dark
    _resetThemeForTests()
    const { current } = useTheme()
    expect(current.value).toBe('dark')
  })

  it('current ignores OS when preference is forced', () => {
    setMatchMedia(true) // OS prefers dark
    _resetThemeForTests()
    const { setPreference, current } = useTheme()
    setPreference('light')
    expect(current.value).toBe('light')
  })

  it('falls back gracefully when localStorage throws', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    const { setPreference, preference } = useTheme()
    expect(() => setPreference('dark')).not.toThrow()
    expect(preference.value).toBe('dark')
    setItemSpy.mockRestore()
  })

  it('falls back to light when matchMedia throws', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: () => {
        throw new Error('not supported')
      },
    })
    _resetThemeForTests()
    const { current } = useTheme()
    expect(current.value).toBe('light')
  })
})
