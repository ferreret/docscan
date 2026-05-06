// Guard puro y testeable que decide redirects en función del rol.
//
// Reglas:
// - Si la ruta destino tiene meta.guest, dejamos pasar (login, accept-invitation).
// - Si el usuario aún no está cargado, dejamos pasar (otros guards de auth deciden).
// - Si la ruta tiene meta.superadmin y el rol no lo es → redirect a /.
// - Si el rol es superadmin y la ruta no empieza por /admin/* → redirect a /admin/tenants.

export interface GuardRoute {
  path: string
  meta: Record<string, unknown>
  name?: string | symbol | null | undefined
}

export interface GuardUser {
  role: string
  tenant_id: number
  email: string
}

export interface RedirectTarget {
  path: string
}

export function enforceRoleAccess(
  to: GuardRoute,
  user: GuardUser | null,
): RedirectTarget | undefined {
  if (to.meta.guest) return undefined
  if (!user) return undefined

  const isAdminRoute = to.path.startsWith('/admin/') || to.path === '/admin'
  const requiresSuperadmin = !!to.meta.superadmin

  if (requiresSuperadmin && user.role !== 'superadmin') {
    return { path: '/' }
  }

  if (user.role === 'superadmin' && !isAdminRoute) {
    return { path: '/admin/tenants' }
  }

  return undefined
}
