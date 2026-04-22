import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ThemeSelector from '@/components/ThemeSelector.vue'
import { _resetThemeForTests } from '@/composables/useTheme'

describe('ThemeSelector', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    _resetThemeForTests()
  })

  it('renders three buttons (light, auto, dark)', () => {
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[0].attributes('aria-label')).toContain('claro')
    expect(buttons[1].attributes('aria-label')).toContain('autom')
    expect(buttons[2].attributes('aria-label')).toContain('oscuro')
  })

  it('marks aria-checked on the active preference', () => {
    localStorage.setItem('theme', 'dark')
    _resetThemeForTests()
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons[0].attributes('aria-checked')).toBe('false')
    expect(buttons[1].attributes('aria-checked')).toBe('false')
    expect(buttons[2].attributes('aria-checked')).toBe('true')
  })

  it('clicking a button calls setPreference with the right value', async () => {
    const wrapper = mount(ThemeSelector)
    await wrapper.findAll('button')[2].trigger('click')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('updates aria-checked reactively after click', async () => {
    const wrapper = mount(ThemeSelector)
    const buttons = wrapper.findAll('button')
    expect(buttons[1].attributes('aria-checked')).toBe('true') // auto default
    await buttons[0].trigger('click')
    expect(buttons[0].attributes('aria-checked')).toBe('true')
    expect(buttons[1].attributes('aria-checked')).toBe('false')
  })
})
