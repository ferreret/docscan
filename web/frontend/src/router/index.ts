import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { enforceRoleAccess } from './roleGuard'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/accept-invitation/:token',
      name: 'accept-invitation',
      component: () => import('@/views/auth/AcceptInvitationView.vue'),
      meta: { guest: true },
      props: true,
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { auth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'applications',
          name: 'applications',
          component: () => import('@/views/applications/ApplicationListView.vue'),
        },
        {
          path: 'applications/:id',
          name: 'application-detail',
          component: () => import('@/views/applications/ApplicationDetailView.vue'),
          props: true,
        },
        {
          path: 'applications/:id/pipeline',
          name: 'pipeline-editor',
          component: () =>
            import('@/views/applications/PipelineEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'applications/:id/events',
          name: 'events',
          component: () =>
            import('@/views/applications/EventsEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'applications/:id/general',
          name: 'general',
          component: () =>
            import('@/views/applications/GeneralConfigEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'applications/:id/image',
          name: 'image',
          component: () =>
            import('@/views/applications/ImageConfigEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'applications/:id/batch-fields',
          name: 'batch-fields',
          component: () =>
            import('@/views/applications/BatchFieldsEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'applications/:id/transfer',
          name: 'transfer',
          component: () =>
            import('@/views/applications/TransferEditorView.vue'),
          meta: { auth: true },
        },
        {
          path: 'batches',
          name: 'batches',
          component: () => import('@/views/batches/BatchListView.vue'),
        },
        {
          path: 'batches/:id',
          name: 'batch-detail',
          component: () => import('@/views/batches/WorkbenchView.vue'),
          props: true,
        },
        {
          path: 'mi-estacion',
          name: 'mi-estacion',
          component: () => import('@/views/MiEstacionView.vue'),
        },
        {
          path: 'team',
          name: 'team',
          component: () => import('@/views/team/TeamView.vue'),
        },
        {
          path: 'admin/tenants',
          name: 'admin-tenants',
          component: () => import('@/views/admin/TenantListView.vue'),
          meta: { superadmin: true },
        },
        {
          path: 'admin/tenants/new',
          name: 'admin-tenant-new',
          component: () => import('@/views/admin/CreateTenantView.vue'),
          meta: { superadmin: true },
        },
        {
          path: 'admin/tenants/:id',
          name: 'admin-tenant-detail',
          component: () => import('@/views/admin/TenantDetailView.vue'),
          props: true,
          meta: { superadmin: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.auth && !token) {
    return { name: 'login' }
  }
  if (to.meta.guest && token) {
    return { name: 'dashboard' }
  }

  if (token) {
    const auth = useAuthStore()
    if (!auth.user) {
      await auth.fetchUser()
    }
    const redirect = enforceRoleAccess(
      { path: to.path, meta: to.meta as Record<string, unknown>, name: to.name },
      auth.user
        ? {
            role: auth.user.role,
            tenant_id: auth.user.tenant_id,
            email: auth.user.email,
          }
        : null,
    )
    if (redirect) {
      return redirect
    }
  }
})

export default router
