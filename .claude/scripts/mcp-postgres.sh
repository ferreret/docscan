#!/usr/bin/env bash
# Wrapper para el MCP server de PostgreSQL.
#
# Lee la URL de conexión desde .env (variable DOCSCAN_WEB_DATABASE__URL),
# le quita el prefijo "+psycopg" que necesita SQLAlchemy pero no acepta el
# servidor MCP, y arranca npx con la URL limpia.
#
# Esto evita committear credenciales en .mcp.json (que sí está tracked).

set -euo pipefail

# Resolver la raíz del proyecto desde la ubicación del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE no existe. Crea .env con DOCSCAN_WEB_DATABASE__URL." >&2
    exit 1
fi

# Extraer la línea de DOCSCAN_WEB_DATABASE__URL del .env sin sourcing
# (más seguro y portable que `source` con set -a).
RAW_URL=$(grep -E '^DOCSCAN_WEB_DATABASE__URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)

if [[ -z "$RAW_URL" ]]; then
    echo "ERROR: DOCSCAN_WEB_DATABASE__URL no definida en $ENV_FILE." >&2
    exit 1
fi

# Quitar comillas si las hubiera
RAW_URL="${RAW_URL%\"}"
RAW_URL="${RAW_URL#\"}"
RAW_URL="${RAW_URL%\'}"
RAW_URL="${RAW_URL#\'}"

# Limpiar el dialecto de SQLAlchemy: postgresql+psycopg:// -> postgresql://
CLEAN_URL="${RAW_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

# Modo dry-run para tests: si DRY_RUN=1, imprime el comando final y sale
if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "npx -y @modelcontextprotocol/server-postgres $CLEAN_URL"
    exit 0
fi

exec npx -y @modelcontextprotocol/server-postgres "$CLEAN_URL"
