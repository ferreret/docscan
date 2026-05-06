# :material-rocket-launch: Inicio rápido (web)

## Acceso al sistema

La aplicación web se sirve desde la URL configurada por la organización (por
ejemplo `https://docscan.miempresa.com`). Al acceder se muestra la pantalla
de login.

## Conceptos fundamentales

La versión web introduce tres conceptos que no existen en la desktop:

### Tenant (inquilino)

Cada organización cliente es un **tenant** independiente. Todos sus datos
(aplicaciones, lotes, usuarios) están aislados de los demás tenants.
Un mismo despliegue puede servir a varios tenants sin que se vean entre sí.

Cada tenant tiene:

- Un **nombre** y un **slug** (identificador URL-safe).
- Un **plan** (`free`, `basic`, `enterprise`) — actualmente informativo.
- Un estado **activo / suspendido** — un tenant suspendido bloquea el
  login de todos sus usuarios.

### Usuario

Cuenta individual con email y contraseña. Pertenece exactamente a un tenant
y tiene un rol asignado. Hereda automáticamente acceso a las aplicaciones y
lotes de su tenant.

### Roles

| Rol | Alcance | Permisos típicos |
|---|---|---|
| `operator` | Su tenant | Trabajar con lotes (escanear, procesar, transferir, indexar). No puede gestionar usuarios. |
| `company_admin` | Su tenant | Todo lo del operador + gestión de usuarios e invitaciones de su tenant + configuración de aplicaciones. |
| `superadmin` | Toda la plataforma | Gestión cross-tenant: crear/suspender/borrar tenants, mover usuarios entre roles, ver auditoría global. |

## Primer acceso

### Si ya tienes cuenta

Introduce email y contraseña en `/login` y entra. La interfaz que verás
depende de tu rol:

- Operador y admin de empresa: barra lateral con `Inicio`, `Aplicaciones`,
  `Lotes` y (admin) `Equipo`.
- Superadmin: barra lateral con `Tenants` (vista cross-tenant). Sin acceso
  a las pantallas de operador.

### Si la organización aún no tiene cuenta

El registro abierto en `/register` crea simultáneamente un tenant nuevo y
su primer usuario admin. Esta vía está pensada para auto-servicio en
despliegues públicos.

!!! note "Despliegues controlados"
    Si la plataforma está pensada solo para clientes invitados, el registro
    abierto puede deshabilitarse — en su lugar, un superadmin crea el
    tenant y su primer admin desde `/admin/tenants/new`.

### Si te invitan a un tenant existente

Tu admin de empresa te enviará un enlace de invitación con un token único.
Al abrirlo, verás un formulario para fijar tu contraseña y entrar al
sistema. La invitación incluye el rol con el que entras.

## Sesión y caducidad

El token JWT que mantiene la sesión caduca por defecto a las 24 horas. Tras
caducar, la API devuelve `401` y la interfaz redirige automáticamente a
`/login`.

## Bloqueo por tenant suspendido

Si tu tenant pasa al estado *suspendido*, todos los logins de ese tenant
se rechazan con un mensaje "Tenant suspendido". Esto incluye intentos de
operador y de admin de empresa — solo el superadmin (que vive en otro
tenant) puede revertirlo desde la pantalla de gestión de tenants.

## Próximos pasos

- [Workbench web](workbench.md) — cómo cargar y trabajar con un lote.
- [Administración](admin.md) — gestión de tenants y usuarios para superadmin.
