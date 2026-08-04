---
name: Sprint superadmin/tenants — CERRADO
description: Sprint completo. 11/11 hitos cerrados (backend hitos 1-6 + frontend 7-10 + smoke/docs 11). Plataforma SaaS multi-tenant operativa con jerarquía superadmin > company_admin > operator.
type: project
originSessionId: 3c3fb8c5-7b21-4ae7-aaee-d12d5eb5a6b5
---
Sprint **superadmin + creación de tenants y usuarios** — primer item del roadmap post-QA. **Cerrado 2026-05-05** (sesión noche del mismo día en que se cerró el backend).

**Why:** Base de plataforma para SaaS. Antes `RegisterView` permitía registro público; ahora sólo TecnoMedia (rol `superadmin`) puede dar de alta tenants. Prerequisito conceptual de AI Mode (gestión API keys por tenant) y útil para cliente local web.

**How to apply:** Sprint cerrado, no quedan tareas. Si en sesión futura aparece un bug de los endpoints/vistas admin: leer este memo + `progreso_2026-05-05.md` (sección "Sesión de noche"). Las decisiones de diseño están abajo. Para retomar el roadmap, leer `project_roadmap_post_qa.md` — siguiente prioridad: cliente local web (TWAIN+transfer).

## Decisiones de diseño consensuadas (referencia)

1. **Jerarquía**: `superadmin (TecnoMedia, cross-tenant) > company_admin (por tenant) > operator`.
2. **Superadmin pertenece al tenant especial "TecnoMedia"** (slug `tecnomedia`, plan `enterprise`). Sus poderes vienen del rol, no de pertenencia. `tenant_id` sigue NOT NULL.
3. **Bootstrap por CLI idempotente**: `python -m web.api.bootstrap superadmin --email X --password Y --display Z`. **Cuidado**: el bootstrap usa regex laxa para email; el endpoint `/auth/login` valida con `EmailStr` y rechaza TLDs reservados (`.test`/`.example`/`.invalid`/`.localhost`) con 422. Usar `.es`, `.com`, `.io`, etc. en credenciales reales.
4. **Registro público eliminado**. `POST /api/auth/register` devuelve 404. `RegisterView.vue` borrada. La aceptación de invitaciones se mantiene.
5. **Sin impersonación en este sprint**. Si se necesita debuggear un cliente, crear company_admin temporal vía `/api/admin/users`.
6. **Auditoría**: tabla `audit_logs` (id, actor_user_id [FK users, nullable], tenant_id [FK tenants, nullable], action, target_type, target_id, payload_json, created_at). Helper `web/api/audit.py::audit(...)` solo `add+flush`. Migración `a3b8d4e2f7c9_add_audit_logs.py`.
7. **Hard-delete tenant cascade real**: rechaza si batches `running`/`transferring` (409); protege TecnoMedia (409); borra applications (cascade BD a batches → pages, history), invitations, users, tenant; limpia archivos del storage.
8. **Plan = enum cerrado** `free | basic | enterprise` (`ALLOWED_PLANS` en `web/api/schemas/admin.py`). Sin lógica de cuotas.
9. **Multi-superadmin permitido** con guard "al menos uno activo". `_check_demote_or_deactivate` cubre tanto último superadmin global como último company_admin del tenant.
10. **Self-modify bloqueado** desde `/api/admin/users` (defense-in-depth): un superadmin no puede modificarse a sí mismo desde aquí — debe pedirlo a otro superadmin o usar `/api/users` (team).

## Backend cerrado — archivos clave

| Archivo | Propósito |
|---|---|
| `web/api/bootstrap.py` | CLI bootstrap. `bootstrap_superadmin(db, *, email, password, display_name)` + argparse. Constantes `TECNOMEDIA_TENANT_NAME/SLUG/PLAN`. |
| `web/api/audit.py` | Helper `audit(db, *, actor, action, target_type, target_id, payload=None)`. |
| `web/api/models.py` | `Tenant`, `User`, `Invitation`, **`AuditLog`**. `ROLE_SUPERADMIN`/`ROLE_COMPANY_ADMIN`/`ROLE_OPERATOR` constantes. |
| `web/api/schemas/admin.py` | `ALLOWED_PLANS`, `ALLOWED_ADMIN_ROLES`, schemas `Tenant*` y `AdminUser*`. |
| `web/api/routers/admin_tenants.py` | 5 endpoints `/api/admin/tenants` con `require_role(ROLE_SUPERADMIN)`. |
| `web/api/routers/admin_users.py` | 4 endpoints `/api/admin/users` cross-tenant con guards. |
| `web/api/main.py` | Mount de los 2 routers en `/api/admin/tenants` y `/api/admin/users` (tag `admin`). |
| `alembic/versions/a3b8d4e2f7c9_add_audit_logs.py` | Migración audit_logs (down_revision `f7c9d2b85a43`). |
| `web/api/auth/router.py` | Endpoint `/register` borrado. `_authenticate` + `get_current_user` rechazan con 401 si `tenant.active=False`. |

## Frontend cerrado — archivos clave

| Archivo | Propósito |
|---|---|
| `web/frontend/src/api/types.ts` | 9 tipos nuevos (`Tenant*`, `AdminUser*`). |
| `web/frontend/src/stores/admin.ts` | `useAdminStore` con CRUD tenants + users cross-tenant. `updateUser`/`deleteUser` refrescan `currentTenant` si coincide. |
| `web/frontend/src/router/roleGuard.ts` | `enforceRoleAccess(to, user)` función pura testeable. |
| `web/frontend/src/router/index.ts` | Rutas `/admin/tenants[/new\|/:id]` con `meta.superadmin`. `beforeEach` async hidrata `auth.user` antes del guard. |
| `web/frontend/src/layouts/AppLayout.vue` | Sidebar dual: "Tenants" + header "TecnoMedia · Administración" si role=superadmin; sidebar normal si no. Atributo `data-superadmin` en `<aside>`. |
| `web/frontend/src/views/admin/TenantListView.vue` | Tabla con stats, toggle Activo, delete con prompt del nombre exacto. |
| `web/frontend/src/views/admin/CreateTenantView.vue` | Form 2 fieldsets, validación local password ≥8, redirect al detalle tras éxito. |
| `web/frontend/src/views/admin/TenantDetailView.vue` | Edita name/plan/active (dirty-aware) + CRUD usuarios + modal crear con `role=dialog` `aria-modal=true`. |

## Endpoints disponibles

```
POST   /api/auth/login                 (rechaza tenant suspendido con 401)
GET    /api/auth/me                    (idem)
POST   /api/auth/token                 (form-data, idem)

GET    /api/admin/tenants              superadmin — paginado + stats
POST   /api/admin/tenants              superadmin — crea tenant + admin
GET    /api/admin/tenants/{id}         superadmin — detalle + users
PATCH  /api/admin/tenants/{id}         superadmin — name | plan | active
DELETE /api/admin/tenants/{id}         superadmin — hard-cascade (BD + storage)

GET    /api/admin/users                superadmin — global, ?tenant_id=
POST   /api/admin/users                superadmin — crear directo en cualquier tenant
PATCH  /api/admin/users/{id}           superadmin — role | active | display_name
DELETE /api/admin/users/{id}           superadmin — con guards
```

## Tests del sprint

- Backend (+81): `test_web_bootstrap.py` (11), `test_web_audit.py` (9), `test_web_admin_tenants.py` (32), `test_web_admin_users.py` (26), `test_web_api.py::TestRegisterRemoved` + `TestTenantSuspended` + helper `_create_tenant_and_admin`.
- Frontend (+49): `tests/stores/admin.store.test.ts` (15), `tests/router/roleGuard.test.ts` (11), `tests/layouts/AppLayout.test.ts` (3), `tests/views/admin/TenantListView.test.ts` (7), `tests/views/admin/CreateTenantView.test.ts` (4), `tests/views/admin/TenantDetailView.test.ts` (12).
- **Suite web total**: backend 298 passing, frontend 460 passing.

## Smoke e2e cerrado

- `scripts/smoke_superadmin.sh` — matriz curl de 21 casos. Ejecuta contra `docker compose up` con bootstrap previo. **21/21 PASS** validados 2026-05-05.
- `docs/screenshots/smoke-superadmin/` — 4 capturas Playwright del flujo visual (listado, crear, detalle, bloqueo del guard como company_admin).
- README sección *"🌐 Versión web SaaS"* con docker compose + bootstrap + jerarquía + referencia al smoke.
- CHANGELOG entrada `[Unreleased]`.

## Patrones aprendidos en el sprint

- **TLD reservados en EmailStr**: el primer bootstrap fue con `super@tecnomedia.test` y todos los logins curl fallaron con 422. La regex de bootstrap es laxa pero `EmailStr` rechaza `.test`/`.example`/`.invalid`/`.localhost`. Usar `.es`/`.com`/etc.
- **Imagen API obsoleta tras añadir módulos**: `web/api/bootstrap.py` no estaba en la imagen porque compose no rebuild automáticamente. `docker compose build api worker` necesario tras cambios estructurales en `web/api`.
- **Hook ruff-format borra imports recién añadidos como "unused"** entre dos `Edit` consecutivos. Workaround: usar `mcp__filesystem__edit_file` para imports cuando el siguiente paso depende de su uso.
- **`trigger('click')` en submit no dispara `submit.prevent`** del form en vue-test-utils. Usar `wrapper.find('form').trigger('submit.prevent')` directo.

## Commits del sprint completo

```
20bbc79  docs: cierra sprint superadmin con smoke + README + CHANGELOG (hito 11)
eebd933  feat(web/frontend): TenantDetailView con CRUD de usuarios (hito 10)
7f9e4d8  feat(web/frontend): TenantListView + CreateTenantView (hito 9)
123129a  feat(web/frontend): rutas /admin + guard de rol + sidebar superadmin (hito 8)
9958d78  feat(web/frontend): store admin + tipos para superadmin (hito 7)
c18af8c  feat(web): routers admin de tenants y usuarios cross-tenant (hitos 5-6)
edbc525  feat(web): añadir AuditLog model + helper audit() (hito 4)
efb94ef  feat(web): preparar plataforma para superadmin (hitos 1-3)
```
