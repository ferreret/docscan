# :material-shield-crown: Administración

La versión web tiene dos niveles de administración: el **admin de empresa**
(`company_admin`) gestiona usuarios y aplicaciones de su tenant, y el
**superadmin** opera por encima de todos los tenants.

## Admin de empresa (`company_admin`)

Hereda todo lo del operador y añade:

- **Pestaña Equipo** en la barra lateral. Lista usuarios del tenant,
  permite invitar nuevos por email, cambiar roles entre `operator` y
  `company_admin`, activar/desactivar y borrar cuentas.
- **Configuración de aplicaciones**. Crear, modificar y borrar
  aplicaciones; editar el pipeline (steps, scripts, eventos lifecycle);
  configurar las opciones de transferencia.

!!! warning "Último admin"
    El sistema impide degradar al último `company_admin` activo del tenant
    a `operator`, y también impide borrarlo o desactivarlo. Hay que
    promocionar a otro usuario primero.

### Invitaciones

Las invitaciones generan un token único que se envía al usuario por email
(o se copia manualmente desde la UI). El destinatario abre el enlace,
fija su contraseña y queda registrado con el rol indicado en la
invitación. Las invitaciones tienen caducidad — al expirar, hay que
reenviarlas.

## Superadmin

Vive fuera del flujo normal de operario y admin de empresa. Su trabajo es
gestionar la plataforma como tal: tenants, usuarios cross-tenant y
auditoría.

### Bootstrap inicial

El primer superadmin se crea desde la línea de comandos con el script de
bootstrap. Es **idempotente**: lanzarlo dos veces con el mismo email no
duplica el usuario ni cambia su contraseña.

```bash
# Dentro del contenedor api (docker compose)
docker compose exec api python -m web.api.bootstrap superadmin \
  --email superadmin@miempresa.com \
  --password "ContraseñaFuerte!" \
  --display "Admin Plataforma"
```

El comando crea (si no existe) el tenant `TecnoMedia` con plan
`enterprise` y el usuario superadmin pertenece a ese tenant. Es el único
tenant cuyo nombre tiene significado especial — los demás son tenants
de cliente normales.

Validaciones del CLI:

- Email con formato válido (regex `[^@\s]+@[^@\s]+\.[^@\s]+`).
- Contraseña de al menos **8 caracteres**.
- Si el email ya existe pero pertenece a otro tenant o tiene otro rol,
  aborta con error.

### Pantalla de gestión de tenants

Tras login, el superadmin entra directamente a `/admin/tenants` (la barra
lateral muestra "Administración" en lugar del tenant del operador).

Funcionalidades:

- **Listado** con estadísticas agregadas por tenant: nº de usuarios,
  aplicaciones y lotes.
- **Crear tenant + primer admin** en una sola operación. El formulario
  recibe nombre, plan, email del admin, nombre visible y contraseña
  inicial. El slug se genera automáticamente del nombre.
- **Editar** nombre y plan.
- **Suspender / activar** desde el botón de la cabecera del detalle.
  Suspender bloquea logins inmediatamente (los usuarios ya autenticados
  mantienen su sesión hasta que caduque el JWT).
- **Borrar tenant**. Borra en cascada usuarios, aplicaciones, lotes,
  páginas y registros de auditoría asociados. Las imágenes en MinIO no
  se borran automáticamente — hay que limpiarlas aparte si es necesario.

### Gestión de usuarios cross-tenant

Endpoint `/admin/users` permite listar, crear y modificar usuarios de
cualquier tenant. La UI dedicada está dentro del detalle de cada tenant
(`/admin/tenants/:id`), donde se ven los usuarios del tenant y se pueden
crear, editar el rol, activar/desactivar o borrar.

### Auditoría

Todas las acciones sensibles quedan registradas en la tabla `audit_logs`:

| Acción | Cuándo se registra |
|---|---|
| `tenant.created` | Crear tenant + primer admin |
| `tenant.updated` | Editar nombre, plan o estado activo/suspendido |
| `tenant.deleted` | Borrar tenant (incluye stats finales) |
| `user.created` | Crear usuario desde admin |
| `user.updated` | Cambio de rol, activo, etc. |
| `user.deleted` | Borrar usuario |

Cada entrada guarda el `actor_user_id` (quién), el `tenant_id` afectado,
el `target_type`/`target_id` y un `payload_json` con el detalle del
cambio. Por ejemplo, una suspensión queda como
`{"changes": {"active": {"from": true, "to": false}}}`.

!!! note "Visualización de auditoría"
    En el momento actual la auditoría solo se consulta directamente
    contra la BD (`SELECT * FROM audit_logs ORDER BY id DESC`). Una
    pantalla dedicada está pendiente para próximas versiones.

## Defense in depth

El control de acceso se aplica en dos capas:

1. **Frontend**: el guard de rutas `enforceRoleAccess` redirige a un
   operador que intente acceder a `/admin/*` hacia la home.
2. **Backend**: cada endpoint `/api/admin/*` exige rol `superadmin`. Si
   un operador con un token válido llama directamente a la API, la
   respuesta es `403 "Rol requerido: superadmin"`.

Esto significa que aunque el usuario evite el frontend, no puede acceder
a recursos cross-tenant.
