import { describe, it, expect } from 'vitest'
import {
  enforceRoleAccess,
  type GuardRoute,
  type GuardUser,
} from '@/router/roleGuard'

const SUPERADMIN: GuardUser = {
  role: 'superadmin',
  tenant_id: 1,
  email: 's@tecnomedia.test',
}
const COMPANY_ADMIN: GuardUser = {
  role: 'company_admin',
  tenant_id: 2,
  email: 'a@acme.test',
}
const OPERATOR: GuardUser = {
  role: 'operator',
  tenant_id: 2,
  email: 'op@acme.test',
}

function r(path: string, meta: Record<string, unknown> = {}): GuardRoute {
  return { path, meta, name: undefined }
}

describe('enforceRoleAccess', () => {
  it('non-superadmin a ruta meta.superadmin: redirect /', () => {
    const result = enforceRoleAccess(r('/admin/tenants', { superadmin: true }), COMPANY_ADMIN)
    expect(result).toEqual({ path: '/' })
  })

  it('operator también es bloqueado de /admin/*', () => {
    const result = enforceRoleAccess(r('/admin/tenants', { superadmin: true }), OPERATOR)
    expect(result).toEqual({ path: '/' })
  })

  it('superadmin en /admin/tenants: pasa', () => {
    const result = enforceRoleAccess(r('/admin/tenants', { superadmin: true }), SUPERADMIN)
    expect(result).toBeUndefined()
  })

  it('superadmin en / (no /admin/*): redirect /admin/tenants', () => {
    const result = enforceRoleAccess(r('/', {}), SUPERADMIN)
    expect(result).toEqual({ path: '/admin/tenants' })
  })

  it('superadmin en /applications: redirect /admin/tenants', () => {
    const result = enforceRoleAccess(r('/applications', {}), SUPERADMIN)
    expect(result).toEqual({ path: '/admin/tenants' })
  })

  it('superadmin en /batches/5: redirect /admin/tenants', () => {
    const result = enforceRoleAccess(r('/batches/5', {}), SUPERADMIN)
    expect(result).toEqual({ path: '/admin/tenants' })
  })

  it('superadmin en /admin/tenants/3: pasa', () => {
    const result = enforceRoleAccess(r('/admin/tenants/3', { superadmin: true }), SUPERADMIN)
    expect(result).toBeUndefined()
  })

  it('user null: deja pasar (otros guards de auth lo manejan)', () => {
    expect(enforceRoleAccess(r('/admin/tenants', { superadmin: true }), null)).toBeUndefined()
    expect(enforceRoleAccess(r('/applications'), null)).toBeUndefined()
  })

  it('company_admin en /applications: pasa (ruta normal)', () => {
    const result = enforceRoleAccess(r('/applications'), COMPANY_ADMIN)
    expect(result).toBeUndefined()
  })

  it('superadmin en /accept-invitation/X: pasa (guest route)', () => {
    const result = enforceRoleAccess(
      r('/accept-invitation/abc123', { guest: true }),
      SUPERADMIN,
    )
    expect(result).toBeUndefined()
  })

  it('superadmin en /login: pasa (guest route)', () => {
    const result = enforceRoleAccess(r('/login', { guest: true }), SUPERADMIN)
    expect(result).toBeUndefined()
  })
})
