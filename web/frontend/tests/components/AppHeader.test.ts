import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'

function makeRouter(initialPath: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/applications', component: { template: '<div/>' } },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications/:id/general', component: { template: '<div/>' } },
      { path: '/applications/:id/pipeline', component: { template: '<div/>' } },
      { path: '/applications/:id/image', component: { template: '<div/>' } },
      { path: '/applications/:id/batch-fields', component: { template: '<div/>' } },
      { path: '/applications/:id/events', component: { template: '<div/>' } },
    ],
  })
  router.push(initialPath)
  return router
}

describe('AppHeader', () => {
  it('renderiza las 6 tabs con la activa correcta según la ruta', async () => {
    const router = makeRouter('/applications/8/events')
    await router.isReady()
    const wrapper = mount(AppHeader, {
      props: { appId: 8, appName: 'Demo' },
      global: { plugins: [router] },
    })
    const tabs = wrapper.findAll('[data-test="app-tab"]')
    expect(tabs).toHaveLength(6)
    expect(tabs[0].text()).toBe('Resumen')
    expect(tabs[1].text()).toBe('General')
    expect(tabs[2].text()).toBe('Pipeline')
    expect(tabs[3].text()).toBe('Imagen')
    expect(tabs[4].text()).toBe('Campos')
    expect(tabs[5].text()).toBe('Eventos')
    expect(tabs[5].classes().join(' ')).toContain('text-primary')
  })

  it('expone un slot "actions" para inyectar botones en la cabecera', async () => {
    const router = makeRouter('/applications/8')
    await router.isReady()
    const wrapper = mount(AppHeader, {
      props: { appId: 8, appName: 'Demo' },
      slots: { actions: '<button data-test="custom-action">Acción</button>' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('[data-test="custom-action"]').exists()).toBe(true)
  })
})
