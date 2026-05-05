import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

async function makeRouter(initialPath: string): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
      { path: '/batches', component: { template: '<div/>' } },
      { path: '/team', component: { template: '<div/>' } },
      { path: '/admin/tenants', component: { template: '<div/>' } },
      { path: '/admin/tenants/:id', component: { template: '<div/>' } },
    ],
  })
  router.push(initialPath)
  await router.isReady()
  return router
}

describe('AppLayout — sidebar por rol', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('superadmin: muestra sólo Tenants y header TecnoMedia · Administración', async () => {
    const router = await makeRouter('/admin/tenants')
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      email: 'super@tecnomedia.test',
      display_name: 'Super',
      role: 'superadmin',
      tenant_id: 1,
      tenant_name: 'TecnoMedia',
    }
    const wrapper = mount(AppLayout, { global: { plugins: [router] } })

    expect(wrapper.find('aside').attributes('data-superadmin')).toBe('true')
    expect(wrapper.text()).toContain('TecnoMedia · Administración')
    expect(wrapper.text()).toContain('Tenants')
    expect(wrapper.text()).not.toContain('Aplicaciones')
    expect(wrapper.text()).not.toContain('Lotes')
    expect(wrapper.text()).not.toContain('Equipo')
    expect(wrapper.text()).not.toContain('Inicio')
  })

  it('company_admin: sidebar normal con Equipo visible', async () => {
    const router = await makeRouter('/')
    const auth = useAuthStore()
    auth.user = {
      id: 5,
      email: 'admin@acme.test',
      display_name: 'Admin',
      role: 'company_admin',
      tenant_id: 2,
      tenant_name: 'Acme',
    }
    const wrapper = mount(AppLayout, { global: { plugins: [router] } })

    expect(wrapper.find('aside').attributes('data-superadmin')).toBe('false')
    expect(wrapper.text()).toContain('Acme')
    expect(wrapper.text()).not.toContain('TecnoMedia · Administración')
    expect(wrapper.text()).toContain('Inicio')
    expect(wrapper.text()).toContain('Aplicaciones')
    expect(wrapper.text()).toContain('Lotes')
    expect(wrapper.text()).toContain('Equipo')
    expect(wrapper.text()).not.toContain('Tenants')
  })

  it('operator: sidebar normal sin Equipo (sólo company_admin lo ve)', async () => {
    const router = await makeRouter('/')
    const auth = useAuthStore()
    auth.user = {
      id: 6,
      email: 'op@acme.test',
      display_name: 'Operador',
      role: 'operator',
      tenant_id: 2,
      tenant_name: 'Acme',
    }
    const wrapper = mount(AppLayout, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('Inicio')
    expect(wrapper.text()).toContain('Aplicaciones')
    expect(wrapper.text()).toContain('Lotes')
    expect(wrapper.text()).not.toContain('Equipo')
    expect(wrapper.text()).not.toContain('Tenants')
  })
})
