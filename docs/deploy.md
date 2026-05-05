# Despliegue local con Docker Compose

Instrucciones para levantar el stack completo de DocScan Studio Web en una
máquina de desarrollo con Docker.

## Pre-requisitos

- Docker Desktop o Docker Engine con el plugin `compose` (v2+)
- ~3 GB de espacio libre para la imagen de la API (incluye opencv, pyzbar,
  zxing-cpp, rapidocr, pymupdf)
- Puertos libres en el host: 5432, 6379, 8001, 9000, 9001

## Arranque rápido

```bash
# 1. Crear el .env en la raíz del proyecto a partir del template
cp web/.env.example .env

# 2. Editar .env y REEMPLAZAR todos los placeholders CHANGE_ME_*
#    por valores reales. Mínimo:
#      - POSTGRES_PASSWORD     → cualquier cadena fuerte
#      - MINIO_ROOT_PASSWORD   → mínimo 8 caracteres
#      - DOCSCAN_WEB_MINIO__SECRET_KEY → idem (debe coincidir con MINIO_ROOT_PASSWORD)
#      - DOCSCAN_WEB_JWT__SECRET_KEY   → openssl rand -hex 32
#
#    Ejemplo de generación automática de la JWT secret:
#    sed -i "s/CHANGE_ME_generate_with_openssl_rand_hex_32/$(openssl rand -hex 32)/" .env

# 3. Arrancar todo
docker compose up --build
```

Si alguna variable obligatoria falta, `docker compose` **se niega a
arrancar** con un mensaje claro: no hay valores por defecto predecibles
en el stack.

En el primer arranque se construye la imagen de la API (~3-5 minutos), se
crean los volúmenes persistentes y se aplican las migraciones Alembic
automáticamente. Cuando veas `Application startup complete`, la API está
lista.

## Servicios expuestos

| Servicio | URL | Credenciales |
|---|---|---|
| API (Swagger) | http://localhost:8001/docs | n/a |
| API (health) | http://localhost:8001/health | n/a |
| MinIO consola | http://localhost:9001 | Las del `.env` (`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`) |
| MinIO S3 API | http://localhost:9000 | idem |
| PostgreSQL | `localhost:5432` | Las del `.env` (`POSTGRES_USER` / `POSTGRES_PASSWORD`) |
| Redis | `localhost:6379` | (sin auth) |

## Verificación con curl

```bash
API=http://localhost:8001

# Health check
curl -s $API/health

# Registrar usuario + crear tenant (sustituye EMAIL y PASSWORD)
EMAIL="admin@example.com"
PASSWORD="<define-una-password-fuerte>"

curl -s -X POST $API/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"display_name\":\"Admin\",\"tenant_name\":\"TestCorp\"}"

# Login y capturar token
TOKEN=$(curl -s -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r .access_token)

# Listar aplicaciones (vacío)
curl -s $API/api/applications -H "Authorization: Bearer $TOKEN"
```

## Comandos útiles

```bash
# Ver logs en tiempo real del API
docker compose logs -f api

# Ver logs de todos los servicios
docker compose logs -f

# Reiniciar solo la API tras un cambio (sin tocar la BD)
docker compose restart api

# Reconstruir la imagen del API tras cambiar deps
docker compose up --build api

# Conectar a la BD directamente
docker compose exec db psql -U docscan -d docscan

# Tumbar todo sin borrar volúmenes (mantiene datos)
docker compose down

# Tumbar todo BORRANDO volúmenes (pierde BD, storage, MinIO)
docker compose down -v

# Ver estado de salud de los servicios
docker compose ps
```

## Estructura de volúmenes

Los datos persisten entre reinicios en volúmenes Docker gestionados:

- `db_data` → `/var/lib/postgresql/data` dentro del contenedor `db`
- `minio_data` → `/data` dentro del contenedor `minio`
- `api_storage` → `/data/storage` dentro del contenedor `api` (ficheros
  subidos a los lotes)

Para inspeccionar el storage filesystem de la API desde el host:

```bash
docker compose exec api ls -la /data/storage
```

## Migrar storage filesystem → MinIO (pendiente)

El stack ya incluye MinIO levantado y listo, pero por ahora la API sigue
usando el storage filesystem (volumen `api_storage`). Cuando se haga la
migración, bastará con cambiar la dependency `FilesystemStorage` por un
`MinIOStorage` y apuntar a `minio:9000` — el compose ya expone esa URL
via `DOCSCAN_WEB_MINIO__ENDPOINT`.

## Troubleshooting

**La API no arranca, error "JWT secret required"**
Falta la variable `DOCSCAN_WEB_JWT__SECRET_KEY` en `.env`. Genérala con:
```bash
echo "DOCSCAN_WEB_JWT__SECRET_KEY=$(openssl rand -hex 32)" >> .env
```

**El API no se conecta a la BD**
Comprueba que en `.env` la URL apunta a `db:5432` (nombre interno del
servicio), NO a `localhost:5432`. El contenedor del API no puede ver el
`localhost` del host.

**`docker compose up` se queda colgado en "creating db"**
El volumen `db_data` puede tener datos de un arranque previo con otra
contraseña. Bórralo con `docker compose down -v` y vuelve a arrancar.

**Puerto 8001/5432/9000 ocupado**
Otro proceso está usando el puerto. Paralo o cambia el mapeo en
`docker-compose.yml`.
