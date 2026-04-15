# Guion de prueba manual — DocScan Studio Web (MVP)

Fecha: 2026-04-15
Rama: `feature/web`

Este documento es para **validar manualmente el MVP web** antes de avanzar con
el envío de invitaciones por email. Se divide en tres secciones: preparación,
escenarios de prueba, y una plantilla de bitácora para anotar lo que
encuentres (errores, fricciones de UX, cosas raras).

No hace falta comprobar cada aserción de backend — los tests automáticos ya
cubren eso. Aquí lo que buscamos es **lo que los tests no ven**: UX, render,
latencia real, flujos completos desde el navegador.

---

## 0. Preparación del entorno

### Opción A — Docker compose (recomendada, más cercana a producción)

```bash
cp web/.env.example .env
# editar .env:
#   POSTGRES_PASSWORD=<algo fuerte>
#   DOCSCAN_WEB_JWT__SECRET_KEY=$(openssl rand -hex 32)
#   MINIO_ROOT_PASSWORD=<mínimo 8 chars>
#   DOCSCAN_WEB_MINIO__SECRET_KEY=<mismo valor que MINIO_ROOT_PASSWORD>

docker compose up --build
```

Esto arranca Postgres + MinIO + Redis + API en `http://localhost:8001`.

En otra terminal, arrancar el frontend:

```bash
cd web/frontend
npm install   # la primera vez
npm run dev
```

Abrir `http://localhost:5173` (puerto por defecto de Vite).

### Opción B — Todo local sin Docker

Solo si ya tienes Postgres corriendo en localhost. Ajusta
`DOCSCAN_WEB_DATABASE__URL` en `.env` y `STORAGE__BACKEND=filesystem`.

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn web.api.main:app --reload --port 8001
# en otra terminal:
cd web/frontend && npm run dev
```

### Material de prueba

- Imágenes de muestra: `docs/sample_docs/peticion_01.png` ... `peticion_06.png`.
- Un PDF cualquiera con varias páginas (si no tienes a mano, genera uno con
  `docs/generate_sample_docs.py`).
- Una imagen **corrupta** (trunca cualquier PNG con `head -c 100 foo.png > corrupt.png`).
- Un PDF **grande** (30+ páginas) si quieres probar latencia real.

---

## 1. Onboarding y autenticación

### 1.1 Registro de tenant nuevo
- [ ] Ir a `/register`, crear tenant con nombre + email admin + password.
- [ ] Verificar que te redirige a login (o auto-login, según esté).
- [ ] Login con las credenciales recién creadas.
- **Observar**: mensajes de error si password es débil, email inválido, tenant
  ya existente. ¿El texto ayuda? ¿Se entiende qué hacer?

### 1.2 Persistencia de sesión
- [ ] Tras login, refrescar la página (F5). La sesión debe mantenerse.
- [ ] Cerrar la pestaña, volver a abrir `localhost:5173`. Idem.
- [ ] Logout explícito. Verifica que rutas protegidas redirigen a login.

### 1.3 Caso de error
- [ ] Login con password incorrecto. ¿El mensaje es claro? ¿Se bloquea tras N
  intentos o no hay límite? (anotar como observación, no como bug necesariamente).

---

## 2. CRUD de aplicaciones

### 2.1 Crear aplicación
- [ ] Desde el dashboard, crear una aplicación nueva con nombre y pipeline por
  defecto.
- [ ] Verificar que aparece en el listado inmediatamente (sin F5).

### 2.2 Editar pipeline
- [ ] Abrir la aplicación, modificar el pipeline (añadir/quitar un paso).
- [ ] Guardar. Salir. Volver a entrar. Los cambios deben persistir.
- **Observar**: ¿el editor de pipeline es usable desde web? ¿qué limitaciones
  notas frente al configurador de escritorio?

### 2.3 Eliminar aplicación
- [ ] Eliminar la aplicación. ¿Pide confirmación? ¿Qué pasa con sus lotes?

---

## 3. Subida y procesamiento de lotes

### 3.1 Lote con imágenes
- [ ] Crear lote vinculado a una aplicación.
- [ ] Subir `peticion_01.png` a `peticion_06.png` (multi-select).
- [ ] Lanzar el pipeline.
- **Observar**:
  - El WebSocket de progreso: ¿la barra avanza suavemente? ¿se queda colgada?
  - Al terminar: **debe aparecer un toast** (éxito o "completado con errores").
  - Tras el toast, los datos de la UI deben refrescarse automáticamente.

### 3.2 Lote con PDF multi-página
- [ ] Subir un PDF de 10+ páginas.
- [ ] Ejecutar pipeline. Medir tiempo total a ojo.
- **Observar**: ¿el progreso por WebSocket refleja página a página? ¿hay un
  salto visual incómodo cuando se crean las N páginas de golpe?

### 3.3 Lote con PDF grande (opcional, estrés)
- [ ] PDF de 30+ páginas.
- **Observar**: ¿la UI sigue respondiendo? ¿puedes navegar a otra pantalla
  mientras procesa? ¿qué pasa si cierras la pestaña a mitad?

### 3.4 Caso de error — archivo corrupto
- [ ] Subir la imagen corrupta preparada.
- **Observar**: ¿qué mensaje da? ¿se cuelga el pipeline o marca la página como
  fallida y continúa? ¿aparece toast de error?

### 3.5 Caso de error — cerrar navegador mid-pipeline
- [ ] Lanzar pipeline sobre lote grande. Cerrar la pestaña a los 2 segundos.
- [ ] Reabrir, ir al lote. ¿El pipeline ha seguido en backend? ¿se reengancha
  el WebSocket al estado actual?

---

## 4. Visor de páginas

### 4.1 Navegación básica
- [ ] Abrir una página procesada. Comprobar que se renderiza la imagen.
- [ ] Zoom in/out (rueda del ratón o botones). Pan con arrastre.
- [ ] Flechas prev/next entre páginas del mismo lote.

### 4.2 Overlays de barcodes
- [ ] Sobre `peticion_01.png` (u otra con barcodes), ver los overlays.
- **Observar**:
  - ¿Los rectángulos están alineados con los códigos de la imagen?
  - Al hacer zoom, ¿se mantienen alineados?
  - Tooltip con el valor del barcode al hover.

### 4.3 Metadatos
- [ ] Ver los campos (`page.fields`) extraídos.
- [ ] Flags de la página (errores de script, avisos, etc.).

---

## 5. Export

### 5.1 Export ZIP
- [ ] Desde un lote terminado, pedir export ZIP.
- [ ] Descargar y abrir el ZIP.
- **Observar**: ¿qué incluye? (imágenes, JSON con metadatos, PDF combinado,
  lo que sea). ¿Es lo que esperarías?

---

## 6. Gestión de equipo

### 6.1 Invitar usuario
- [ ] Ir a Team. Invitar un email nuevo.
- [ ] Verificar que la invitación aparece en el listado (pendiente).
- **Nota**: hoy **no se envía email**. Para probar el flujo del invitado,
  tienes que sacar el token manualmente:
  ```bash
  docker exec -it docscan-web-db psql -U docscan -d docscan \
    -c "SELECT token FROM invitations ORDER BY created_at DESC LIMIT 1;"
  ```
  Y abrir `http://localhost:5173/accept-invitation?token=<token>` en modo
  incógnito.

### 6.2 Aceptar invitación
- [ ] Desde ventana incógnita, abrir el link. Completar datos (nombre, password).
- [ ] Login con el nuevo usuario. Debe ver los recursos del mismo tenant.

### 6.3 Listado de usuarios
- [ ] En Team, ver los dos usuarios (admin original + invitado).
- [ ] Probar revocar la invitación de un tercer email antes de aceptarla.

### 6.4 Paginación (revisar "a ciegas")
- Los endpoints ya paginan (50 por página). Como el frontend aún no tiene UI
  de paginación, solo verás los primeros 50. No bloqueante, solo anotar si
  notas algo raro.

---

## 7. Multi-tenant — aislamiento

Crítico: los tenants no deben verse entre sí.

- [ ] Registra un **segundo tenant** con otro email.
- [ ] Desde ese tenant, intenta acceder a una URL directa de un lote del
  primer tenant (copia el UUID del lote de la URL del primero).
- **Esperado**: 404 (no 403, no 200 con los datos). Si ves los datos del
  otro tenant: **bug crítico, anotar inmediatamente**.

---

## 8. Bitácora

Copia esta tabla y rellénala mientras pruebas. No hace falta que sea
exhaustiva — lo importante es capturar todo lo que te haga dudar.

| # | Sección | Qué hice | Qué pasó | Gravedad (bloq/alto/medio/bajo/UX) |
|---|---------|----------|----------|------------------------------------|
| 1 |         |          |          |                                    |
| 2 |         |          |          |                                    |

**Gravedad orientativa:**
- **bloq**: impide continuar la prueba o compromete seguridad (ej. fuga multi-tenant).
- **alto**: función clave roto pero hay workaround.
- **medio**: funciona pero con comportamiento raro.
- **bajo**: cosa menor.
- **UX**: no es un bug, es una fricción o mejora de experiencia.

Al terminar, pásame la bitácora y priorizamos.
