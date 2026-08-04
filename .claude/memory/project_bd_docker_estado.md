---
name: Estado BD docker tras rebuild 2026-05-11
description: BD docker reseteada parcialmente. Tenant TecnoMedia, app AppHito7, operario con password <REDACTADO — ver gestor de contraseñas>. Útil para próximos smokes.
type: project
originSessionId: f19935ac-e52e-4b9e-879a-36b3000ed3f0
---
La BD docker no contiene los datos antiguos descritos en MEMORY.md (tenant SmokeTest, app SmokePipeline) — fue recreada o limpiada entre 2026-05-08 y 2026-05-11. Estado real al cierre de sesión 2026-05-11:

**Why:** las imágenes `docscan-api` y `docscan-worker` se construyeron con código pre-hito-13 (anteriores a las migraciones `d4e8f6a9b132` y `e6f9a013c245`). Al levantar el stack hoy, las columnas `scan_show_dialog` y `scan_defaults_json` no existían y el smoke falló silenciosamente (el handler PATCH ignoraba los campos y el front cae al modo direct/back-compat). Solución aplicada: `docker compose build api worker` + `up -d` + `alembic upgrade head` desde el container api.

**How to apply:**

Para el siguiente smoke o cualquier prueba contra docker:

- **Login**: `operario@tecnomedia.es` / `<REDACTADO — ver gestor de contraseñas>` (rol operator, tenant TecnoMedia id=2). Password reseteado en esta sesión vía UPDATE de `hashed_password` (columna se llama `hashed_password`, NO `password_hash`).
- También existe `superadmin@tecnomedia.es` (rol superadmin) con password desconocido. Resetear con mismo procedimiento si hace falta superadmin.
- **App de pruebas**: `AppHito7` (id=2) con `scan_show_dialog=true`, `scan_defaults_json='{}'`.
- **Lotes existentes**: ids 2-6 con páginas 5-17. El lote 6 (último) tiene páginas 16-17 escaneadas con mode=Lineart (overrides del dialog del hito 13).
- **Imágenes**: en bucket MinIO `docscan` con path `2/<batch_id>/<hash>.png`. Verificable con `docker compose exec minio mc ls --recursive local/docscan/` tras configurar alias `mc alias set local http://localhost:9000 docscan docscan123`.
- **HEAD alembic**: `e6f9a013c245` (última migración del hito 13).
- **Vite proxy**: el frontend en `:5173` proxea `/api` a `localhost:8001` (API). El agente local (puerto 47816) pasa el SaaS URL como `http://localhost:5173` al hacer pair, así que los uploads del agente van `:5173/api/...` (vía proxy de vite).

Hash bcrypt para password "<REDACTADO — ver gestor de contraseñas>" (cacheado por si hay que volver a aplicar):
`<HASH BCRYPT REDACTADO>`

Para resetear vía heredoc (NO usar `-c` con escapes — el shell expande mal los `$`):
```bash
docker compose exec -T db psql -U docscan -d docscan <<'EOF'
UPDATE users SET hashed_password='<HASH BCRYPT REDACTADO>'
WHERE email='operario@tecnomedia.es';
EOF
```

Si haces rebuild de imágenes (`docker compose build api worker`), verifica que las migraciones se aplican: `docker compose exec api alembic heads` debe coincidir con `docker compose exec db psql ... -c "SELECT version_num FROM alembic_version;"`.
