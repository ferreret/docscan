# Cheatsheet de demo — DocScan Studio Web

> Referencia rápida para la demo al jefe. Tener este fichero abierto en
> otra ventana mientras conduces la demo.

## URLs y credenciales

| Recurso | URL / dato |
|---|---|
| Frontend | `http://localhost:5173/` |
| API (uso interno, no enseñar) | `http://localhost:8001/health` |
| MinIO consola (uso interno) | `http://localhost:9001/` |
| **TestCo** (tenant principal de la demo) | `admin@testco.com` / *(password reseteada para la sesión de QA — pedir al operador)* |
| **OtherCo** (para demo de aislamiento multi-tenant) | `admin@otherco.com` / *(idem)* |

## Estado del escenario

**Aplicación "App de prueba"** en TestCo configurada con:

- **Pipeline**: AutoDeskew → Resize (max 2000px) → Barcode Motor 1 → Script "marcar revisión si no hay barcodes".
- **Transfer**: modo carpeta, destino `/tmp/demo-out` (dentro del contenedor API), formato PNG.
- **Batch fields**: cliente (texto, requerido), fecha_alta (fecha), prioridad (lista), numero_pedido (numérico, requerido).
- **Eventos lifecycle**: vacíos (mostrar el editor pero sin scripts activos).

**Lotes preparados**:

| Lote | Estado | Páginas | Para qué sirve en la demo |
|---|---|---|---|
| **#1** | `read` | 6 | Demo principal del **workbench**. Ya procesado. Página #4 marcada para revisión, #6 excluida. Metadata limpia (ACME Corporación · 28/04/2026 · Media, urgente · 1024). |
| **#4** | `read` | 4 | Demo de **export ZIP** (descarga rápida, ~30 MB). |
| **#5** | `created` | 4 | Demo de **F5 pipeline run en vivo**. Tras pulsar F5, pasará a `read` y dos páginas quedarán marcadas para revisión (las que no tienen barcode). |

> Si quieres re-resetear el lote #5 entre demos:
> ```bash
> docker exec docscan-web-db psql -U docscan -d docscan -c \
>   "UPDATE batches SET state='created' WHERE id=5; \
>    UPDATE pages SET pipeline_processed=false, needs_review=false WHERE batch_id=5; \
>    DELETE FROM barcodes WHERE page_id IN (SELECT id FROM pages WHERE batch_id=5);"
> ```

## Guion de demo (15-20 min)

### 1. Posicionamiento (1 min)

> "DocScan Studio: dos sabores. **Desktop** estable con instaladores
> Linux+Windows; **web SaaS** multi-tenant que es lo que enseñamos hoy.
> Mismo pipeline core, frontend distinto."

### 2. Login y aislamiento (2 min)

1. Login `admin@testco.com`. Ves 3 lotes de TestCo.
2. Cierra sesión (icono de la esquina inferior izquierda).
3. Login `admin@otherco.com`. Ves 0 lotes.
4. Vuelve a `admin@testco.com`. **Mensaje**: "Cada empresa vive aislada.
   Cualquier intento cruzado devuelve 404 — no se filtra ni la
   existencia de recursos."

### 3. Workbench (8-10 min) — abrir Lote #1

| Acción | Qué decir |
|---|---|
| Click en Lote #1 | "Esta es la pantalla de operador. Miniaturas, visor, panel de barcodes y metadata del lote." |
| Pulsar `?` | "16 atajos en 4 categorías. Diseño pensado para captura masiva sin ratón." |
| Cerrar modal con Esc, navegar con `←`/`→` | "Navegación lateral." |
| Pulsar `M` en página #2 | "Marca para revisión: borde amarillo en visor + badge en thumb." |
| Pulsar `M` otra vez | "Toggle." |
| Pulsar `X` en otra | "Excluir. Borde rojo, no irá a transferencia." |
| `Shift+→` | "Salta a la siguiente marcada para revisión. Si no hay, te lo dice." |
| Pulsar `R` | "Rotar. La imagen del visor gira; el thumb se actualiza al instante." |
| Volver a rotar 3 veces | "Lossless en backend (Pillow), preserva DPI." |
| Drag thumb #2 a posición #4 | "Reordenar visualmente. Persiste en BD vía POST /reorder." |
| Click en `+ Añadir` (panel barcodes) | "Barcode manual cuando el detector falla." Cancelar. |
| Editar `cliente` | "Metadata del lote." |
| Cambiar a tab LOG | "Log en tiempo real. Aparecerán mensajes de pipeline, transferencia, scripts." |

### 4. Pipeline run en vivo (2-3 min) — Lote #5

1. Volver a `Lotes`, abrir Lote #5 (`created`).
2. Pulsar `F5` o botón **▶ Pipeline**.
3. Estado pasa de `created` a `read` en segundos.
4. Volver a thumbs: dos páginas tienen badge ⚐ (las que no tenían
   barcode → el script las marcó para revisión).
5. **Mensaje**: "El pipeline es configurable por aplicación. Aquí
   tenemos AutoDeskew, Resize, detección de códigos y un script Python
   que marca como revisión las páginas sin código."

### 5. Export ZIP y transferencia (2 min)

1. Sin salir del Lote #5, pulsar **↓ ZIP**. Se descarga `batch_5.zip`.
2. Abrir el ZIP en el navegador o explorador de archivos:
   `pages/page_NNNN.png` + `manifest.json` con metadata, fields,
   barcodes y OCR.
3. **Mensaje**: "Export universal para retener el lote. Para integración
   real con sistemas internos, configuramos transfers."
4. Pulsar **↗ Transferir** o tecla `T`.
5. En terminal aparte (si procede):
   ```bash
   docker exec docscan-web-api ls /tmp/demo-out/batch_5/
   ```
   Aparecen los 4 PNG. **Mensaje**: "Aquí lo enseño dentro del
   contenedor; en producción el destino es lo que defina cada cliente:
   carpeta de red, S3, FTP."

### 6. Configurador (3 min)

1. Click en `Aplicaciones` → `App de prueba`.
2. Recorrer las pestañas:
   - **Resumen**: estado, formato salida, auto-transferencia, lotes.
   - **Pipeline**: enseñar los 4 steps configurados. Click en `+ Añadir
     step` → "Aquí elegimos entre Barcode, ImageOp, OCR y Script Python.
     Pipeline 100% configurable sin tocar código fuente."
   - **Imagen**: ajustes globales (DPI, color).
   - **Campos**: definición de batch_fields (la metadata que se ve en
     el workbench).
   - **Transferencia**: ya configurado.
   - **Eventos**: editor de scripts lifecycle (`on_batch_loaded`,
     `on_page_changed`, etc.) con plantilla y panel de variables. "Si
     necesitan reglas de negocio específicas — validación, integración
     con ERP, alertas — se escriben aquí en Python."

### 7. Equipo (1 min)

1. Click en `Equipo`.
2. Listado de miembros: tú como `company_admin`.
3. Click en `+ Invitar usuario`. Email `nuevo@testco.com`, rol
   `operator`. Genera link de aceptación.
4. **Mensaje**: "Roles: company_admin (acceso total) y operator
   (CRUD de lotes, sin configurador). Auto-protección: nadie puede
   desactivarse a sí mismo, eliminarse, ni dejar al tenant sin admins."
5. Revocar la invitación recién creada.

### 8. Cierre (1 min) — métricas

> "1427 tests automatizados (859 desktop + 201 backend + 367 frontend).
> Multi-tenancy auditado E2E. Bitácora QA con 38 entradas cerradas al
> 100%. Próxima fase: notificaciones, multi-usuario simultáneo en mismo
> lote, backup/restore."

## Preguntas previsibles del jefe — respuestas

| Pregunta | Respuesta corta |
|---|---|
| "¿Cuánto cuesta operar un tenant?" | Postgres + MinIO + Redis + API + frontend. Stack barato; en cloud, ~10-30 €/mes por tenant medio. |
| "¿Soporta firmas digitales en PDF?" | Hoy no. PDF/A está pensado en el desktop. La web hace export PNG/PDF; firmas se añadirían como step de pipeline. |
| "¿Dónde se guardan las imágenes?" | MinIO (S3-compatible). En despliegue on-premise, podemos apuntar a un disco; en cloud, S3 real. Cada tenant tiene su prefijo de path. |
| "¿Qué pasa si cae la conexión durante un upload?" | El POST de páginas es atómico por fichero. Si falla, el lote no recibe esa página y el usuario lo reintenta. |
| "¿Es accesible WCAG?" | Atajos cumplidos, role/aria-modal en todos los dialogs (regresión cerrada en QA), navegación con teclado completa. Pendiente auditoría WCAG formal. |
| "¿Y la velocidad con lotes grandes?" | Probado con 21 páginas sin problema. El bottleneck es el navegador renderizando thumbs; para 200+ páginas habría que paginar el panel lateral. |
| "¿Y si quiero auto-transferir tras pipeline?" | Toggle `auto_transfer` en la aplicación: tras `pipeline_completed`, dispara transfer automático. |

## Cosas que NO mostrar / evitar

- **No** abras el Lote #2 (es de QA Company, no aparece en TestCo —
  bien, pero si por error pinchas la URL `/batches/2` da 404 y queda
  raro).
- **No** muestres `Ctrl+G` (atajo de "script de navegación custom"): no
  hay handler en App de prueba.
- **No** hables de Celery / ARQ: Redis está levantado pero sin worker
  activo; transfer y pipeline corren en el mismo proceso de la API por
  ahora.
- **No** te metas en docker-compose.yml ni Dockerfile a menos que
  pregunten explícitamente.
- **Si dice "está en modo claro"**: cambia tema en el selector de la
  esquina inferior izquierda (☀ / ◐ / ☾). El oscuro vende mejor.

## Comandos para tener a mano

```bash
# Estado del stack
docker compose ps

# Logs API en vivo (en otra ventana)
docker logs -f docscan-web-api

# Reset rápido del lote #5 entre intentos de F5
docker exec docscan-web-db psql -U docscan -d docscan -c \
  "UPDATE batches SET state='created' WHERE id=5; \
   UPDATE pages SET pipeline_processed=false, needs_review=false WHERE batch_id=5; \
   DELETE FROM barcodes WHERE page_id IN (SELECT id FROM pages WHERE batch_id=5);"

# Limpiar carpeta de transferencia entre demos
docker exec docscan-web-api rm -rf /tmp/demo-out/batch_5

# Ver lo transferido tras T
docker exec docscan-web-api ls -la /tmp/demo-out/

# Para apagar todo cuando termines
docker compose down
# (el frontend dev se mata con Ctrl+C en su terminal)
```
