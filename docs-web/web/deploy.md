# :material-server: Despliegue

Instrucciones para levantar el stack completo de DocScan Studio Web con
Docker Compose.

## Pre-requisitos

- Docker Desktop o Docker Engine con plugin `compose` v2+.
- ~3 GB libres para la imagen de la API (incluye opencv, pyzbar,
  zxing-cpp, rapidocr, pymupdf, anthropic SDK).
- Puertos libres en el host: `5432`, `6379`, `8001`, `9000`, `9001`.

## Arranque rápido

```bash
# 1. Crear el .env en la raíz del proyecto a partir del template
cp web/.env.example .env

# 2. Editar .env y reemplazar todos los placeholders CHANGE_ME_*
#    Mínimos obligatorios:
#      POSTGRES_PASSWORD              cualquier cadena fuerte
#      MINIO_ROOT_PASSWORD            mínimo 8 caracteres
#      DOCSCAN_WEB_MINIO__SECRET_KEY  debe coincidir con MINIO_ROOT_PASSWORD
#      DOCSCAN_WEB_JWT__SECRET_KEY    openssl rand -hex 32

# 3. Arrancar todo el stack
docker compose up --build
```

Si alguna variable obligatoria falta, `docker compose` se niega a arrancar
con mensaje claro: no hay valores por defecto predecibles, todo debe
declararse explícitamente.

En el primer arranque se construye la imagen de la API (~3-5 min), se
crean los volúmenes persistentes y se aplican las migraciones Alembic
automáticamente. El log "Application startup complete" indica que la
API está lista.

## Servicios expuestos

| Servicio | URL | Descripción |
|---|---|---|
| API + Swagger | http://localhost:8001/docs | OpenAPI generado, útil para probar endpoints |
| API health | http://localhost:8001/health | Devuelve `{"ok": true}` si está viva |
| MinIO consola | http://localhost:9001 | UI de administración del storage S3 |
| MinIO S3 API | http://localhost:9000 | Endpoint S3-compatible para clientes |
| PostgreSQL | `localhost:5432` | BD principal |
| Redis | `localhost:6379` | Cola de jobs ARQ (sin auth) |

## Servicios Docker en juego

```
docscan-web-db        postgres:16-alpine     puerto 5432
docscan-web-redis     redis:7-alpine          puerto 6379
docscan-web-minio     minio/minio:latest     puertos 9000, 9001
docscan-web-api       imagen propia          puerto 8001
docscan-web-worker    misma imagen           comando arq WorkerSettings
```

El servicio `worker` ejecuta `arq web.api.tasks.worker.WorkerSettings` y
procesa los jobs encolados por la API: `pipeline_job` (procesar lote),
`transfer_job` (transferir lote) y `recovery_job` (recuperar lotes
huérfanos al arrancar). Comparte la imagen Docker con la API — solo
cambia el `command`.

## Bootstrap del primer superadmin

Tras el primer arranque hace falta crear un usuario superadmin para poder
gestionar tenants. Es un comando idempotente:

```bash
docker compose exec api python -m web.api.bootstrap superadmin \
  --email superadmin@miempresa.com \
  --password "ContraseñaFuerte!" \
  --display "Admin Plataforma"
```

Crea el tenant `TecnoMedia` (si no existe) y un usuario con rol
`superadmin` dentro de él. Lanzarlo dos veces no duplica nada.

## Frontend en desarrollo

Para ejecutar el frontend Vue 3 en modo dev contra el stack:

```bash
cd web/frontend
npm install
npm run dev
# Disponible en http://localhost:5173 con proxy a http://localhost:8001/api
```

Para producción se construye con `npm run build` y se sirve estáticamente
desde un nginx u otro servidor web — el dist queda en `web/frontend/dist/`.

## Recovery automático

Cuando la API arranca, encola un único `recovery_job` que ejecuta una
operación `UPDATE` masiva sobre la tabla `batches`: cualquier lote en
estado `running` o `transferring` (que probablemente quedó huérfano por
una caída) pasa a `error_read` para que un operador lo reabra
manualmente.

Esto es defensa en profundidad: si el worker o la API caen mientras
había procesamiento en marcha, el siguiente arranque limpia el estado
sin perder datos.

## Comandos útiles

```bash
# Logs en tiempo real
docker compose logs -f api
docker compose logs -f worker

# Estado de los servicios
docker compose ps

# Reiniciar solo la API (sin tocar BD)
docker compose restart api

# Conectar a la BD directamente
docker compose exec db psql -U docscan -d docscan

# Inspeccionar MinIO desde dentro
docker compose exec minio mc alias set local http://localhost:9000 \
  "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
docker compose exec minio mc ls local/docscan/

# Tumbar manteniendo datos
docker compose down

# Tumbar BORRANDO datos (BD, storage, MinIO)
docker compose down -v
```

## Volúmenes persistentes

| Volumen | Punto de montaje | Contenido |
|---|---|---|
| `db_data` | `/var/lib/postgresql/data` (db) | PostgreSQL |
| `minio_data` | `/data` (minio) | Páginas e imágenes de los lotes |
| `api_storage` | `/data/storage` (api) | Storage filesystem alternativo (legacy) |

## Backup mínimo

Para un backup básico del stack en producción:

```bash
# Dump de la BD
docker compose exec -T db pg_dump -U docscan docscan > backup.sql

# Sincronizar el bucket MinIO a un disco local
docker compose exec minio mc mirror local/docscan /backup-minio/
```

Restaurar es el mismo proceso al revés (`psql < backup.sql` y
`mc mirror /backup-minio/ local/docscan`). Para producciones serias
considera Postgres con replicación y MinIO con replicación de bucket.

## Troubleshooting

**La API no arranca, error "JWT secret required"**
:   Falta la variable `DOCSCAN_WEB_JWT__SECRET_KEY` en `.env`. Genérala con
    `echo "DOCSCAN_WEB_JWT__SECRET_KEY=$(openssl rand -hex 32)" >> .env`.

**API no conecta a la BD**
:   Verifica que `DATABASE__URL` apunta al hostname interno `db:5432`,
    NO a `localhost:5432`. El contenedor de la API no ve el `localhost`
    del host.

**`docker compose up` cuelga al crear la BD**
:   El volumen `db_data` puede tener datos de un arranque previo con
    otra contraseña. Bórralo con `docker compose down -v` y vuelve a
    arrancar (perderás los datos previos).

**Worker registra `ImportError` al arrancar**
:   Suele ser un caso de relaciones SQLAlchemy no resueltas. El módulo
    `web/api/_register_models.py` carga todos los modelos por
    side-effect; tanto la API como el worker deben importarlo antes
    del primer query. Revisa que el `worker.py` lo importe.

**Puerto 8001 / 5432 / 9000 ocupado**
:   Otro proceso usa el puerto. Páralo o cambia el mapeo en
    `docker-compose.yml`.
