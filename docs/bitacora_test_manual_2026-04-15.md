# Bitácora de prueba manual — 2026-04-15

Rama: `feature/web` · Ejecuta: Nicolás · Registra: Claude

## Leyenda de gravedad
- **bloq**: impide continuar la prueba o compromete seguridad.
- **alto**: función clave rota pero hay workaround.
- **medio**: funciona pero con comportamiento raro.
- **bajo**: cosa menor.
- **UX**: fricción o mejora de experiencia, no un bug funcional.

## Incidencias

| # | Sección | Síntoma | Gravedad | Estado |
|---|---------|---------|----------|--------|
| 1 | 1.1 Registro | El error 422 de pydantic se muestra como JSON crudo en la caja de error del frontend (`[ { "type": ..., "msg": ...} ]` literal). | medio / UX | **Corregido en sesión** — `web/frontend/src/api/client.ts` ahora formatea `detail` cuando es array (`formatDetail`). |
| 2 | 1.1 Registro | Mensajes de validación de email provenientes de pydantic siguen en inglés tras formatear. | bajo / UX | Pendiente |
| 3 | 1.1 Registro | **El registro acepta contraseñas de 3 caracteres** (probado con `123`). No hay validación de longitud/complejidad ni en frontend ni en backend. | alto (seguridad) | **Corregido** — `RegisterRequest.password` ahora usa `Field(min_length=8)` (coherente con `AcceptInvitationRequest`). Frontend añade `minlength="8"` y label "Mínimo 8 caracteres". Test de regresión nuevo (`test_registro_password_corta_422`). |
| 4 | 1.1 → 1.2 Login | Un 401 de `/api/auth/login` disparaba `window.location.href = '/login'` en `client.ts`, recargando la página y borrando el mensaje de error. El usuario veía "no pasa nada". | alto / UX | **Corregido** — el redirect solo se dispara si había token previo (expiración de sesión), no si aún no estabas logado. |

| 5 | 2.2 Editar app | **No hay editor de pipeline en el frontend web.** La vista `/applications/:id` solo muestra metadatos (estado, formato de salida, auto-transferencia, lotes). El pipeline se edita únicamente desde el configurador de escritorio. | limitación funcional | Pendiente (decisión de producto: ¿se añade al MVP web o se mantiene así?) |
| 6 | 4.2 Overlays | El visor abre correctamente y muestra la imagen, pero no se ven overlays de barcodes. Causa: el pipeline por defecto de una app nueva no incluye `BarcodeStep`, y desde web no se puede editar. Dependencia de #5. | limitación (no bug) | Pendiente |
| 7 | 1.3 Login | No hay rate limiting visible en el endpoint `/api/auth/login`. | bajo (seguridad) | Pendiente |

## Tests ejecutados

| Test | Resultado | Notas |
|------|-----------|-------|
| 1.1 Registro | ✅ PASS tras fixes #1 y #4 | |
| 1.2 Persistencia de sesión | ✅ PASS | F5 mantiene, nueva pestaña mantiene, logout redirige |
| 1.3 Errores de login | ✅ PASS | Mismo mensaje para pass mal y email inexistente (buena práctica) |
| 2.1 Crear app | ✅ PASS | |
| 2.2 Editar pipeline | ⚠️ N/A | Ver #5 |
| 2.3 Eliminar app | ⏭️ pendiente | |
| 3.1 Lote con imágenes + pipeline | ✅ PASS | 6 páginas, `created` → `read`, WebSocket OK |
| 3.2 Lote con PDF | ⏭️ pendiente | |
| 3.3 Lote grande (estrés) | ⏭️ pendiente | |
| 3.4 Archivo corrupto | ⏭️ pendiente | |
| 4.1 Visor navegación | ✅ PASS | Next/prev/zoom/cerrar funcionan |
| 4.2 Overlays barcode | ⚠️ N/A | Ver #6 |
| 5.1 Export ZIP | ✅ PASS | 6 PNG + manifest.json, 465 KB |
| 6.1 Invitar usuario | ✅ PASS | Link generado, visible en UI para compartir manualmente |
| 6.2 Aceptar invitación | ⏭️ pendiente | |
| **7 Aislamiento multi-tenant** | ✅ **PASS COMPLETO** | Todos los accesos cross-tenant (batch, pages, image, app, export) devuelven 404 |

## Errores fixeados en entorno (no cuentan como bug del producto)
- Migración `4a90ab536830`: `server_default=sa.text('0')` sobre Boolean rompía en Postgres (ok en SQLite). Cambiado a `sa.false()`.
- CORS: frontend arranca en puerto 5180 (el 5173 lo ocupa otro proyecto). Añadido `http://localhost:5180` a `DOCSCAN_WEB_CORS_ORIGINS` vía `docker-compose.yml`.
