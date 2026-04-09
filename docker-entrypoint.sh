#!/usr/bin/env bash
# Entrypoint del contenedor de la API web.
#
# Inicializa la BD (create_all la primera vez, alembic upgrade head después)
# y arranca uvicorn. Pensado para ejecutarse tras un `docker compose up`.

set -euo pipefail

echo "[entrypoint] Inicializando BD..."
python /app/docker-bootstrap-db.py

echo "[entrypoint] Arrancando uvicorn en 0.0.0.0:8001..."
exec uvicorn web.api.main:create_app --factory --host 0.0.0.0 --port 8001
