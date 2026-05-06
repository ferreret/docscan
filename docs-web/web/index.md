# :material-web: Versión Web SaaS

DocScan Studio dispone de una **versión web multi-tenant** complementaria a la
aplicación desktop. Comparte el motor de pipeline, scripting y reconocimiento,
pero se accede desde el navegador y soporta varios usuarios simultáneos
organizados por **inquilino** (*tenant*).

!!! warning "Estado del proyecto"
    La versión web está en desarrollo activo. La interfaz puede cambiar entre
    versiones. Esta sección de la documentación se mantendrá actualizada con
    las funcionalidades estables.

## Diferencias clave con la versión desktop

| Aspecto | Desktop | Web SaaS |
|---|---|---|
| **Despliegue** | Instalador por máquina | Servidor central (Docker Compose) |
| **Usuarios** | Mono-puesto, sin login | Multi-usuario con login JWT |
| **Multi-tenancy** | No aplica | Aislamiento total por tenant |
| **Storage** | Disco local | PostgreSQL + MinIO (S3-compatible) |
| **Procesamiento** | Hilo Qt en el cliente | Worker ARQ en el servidor |
| **Tiempo real** | Señales Qt | WebSocket |
| **Escáner** | Acceso directo al hardware | Pendiente — cliente local en roadmap |
| **Transferencia local** | Acceso directo al sistema de archivos | Pendiente — cliente local en roadmap |

## Cuándo elegir cada una

**Desktop** sigue siendo la opción cuando:

- El cliente trabaja desde una sola estación con escáner conectado.
- No hay necesidad de compartir lotes ni gestionar usuarios.
- El equipo prefiere evitar instalar/mantener un servidor.

**Web SaaS** es la opción cuando:

- Hay varias personas trabajando con los mismos lotes o aplicaciones.
- Se requiere control de acceso por roles (operador, admin de empresa,
  superadmin).
- La organización prefiere un único punto de gestión central.
- Se quiere escalar a varias empresas (clientes) desde un único despliegue.

## Componentes del despliegue

```
                           ┌─────────────────────┐
                           │  Navegador Vue 3    │
                           │  (operario / admin) │
                           └──────────┬──────────┘
                                      │ HTTPS
                                      │
   ┌──────────────────────────────────▼──────────────────────────────────┐
   │  API FastAPI                                                        │
   │  - Auth JWT, multi-tenancy, RBAC                                    │
   │  - Endpoints REST + WebSocket de eventos                            │
   │  - Encola jobs (pipeline, transfer) en ARQ                          │
   └─────┬─────────────┬───────────────┬─────────────────────────────────┘
         │             │               │
   ┌─────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐ ┌──────────────────┐
   │PostgreSQL │ │   Redis   │ │    MinIO    │ │  ARQ worker      │
   │ tenants,  │ │ cola jobs │ │  S3 storage │ │ procesa pipeline │
   │ users,    │ │           │ │  de páginas │ │ y transferencias │
   │ batches…  │ │           │ │             │ │                  │
   └───────────┘ └───────────┘ └─────────────┘ └──────────────────┘
```

## Recorrido por la sección

- [Inicio rápido](getting-started.md) — login, registro y conceptos básicos
  de tenant/usuario/rol.
- [Workbench web](workbench.md) — el equivalente navegador del workbench
  desktop, con sus diferencias.
- [Administración](admin.md) — superadmin, gestión de tenants, usuarios y
  auditoría.
- [Despliegue](deploy.md) — Docker Compose, variables de entorno y
  arranque inicial.
