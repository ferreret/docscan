import { createRouter, createWebHistory } from 'vue-router'

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
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
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
          path: 'batches',
          name: 'batches',
          component: () => import('@/views/batches/BatchListView.vue'),
        },
        {
          path: 'batches/:id',
          name: 'batch-detail',
          component: () => import('@/views/batches/BatchDetailView.vue'),
          props: true,
        },
        {
          path: 'team',
          name: 'team',
          component: () => import('@/views/team/TeamView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.auth && !token) {
    return { name: 'login' }
  }
  if (to.meta.guest && token) {
    return { name: 'dashboard' }
  }
})

export default router
