---
name: progreso-doc
description: Genera el informe diario de progreso para el jefe (docs/progreso_YYYY-MM-DD.md). Obligatorio al final de cada sesión según CLAUDE.md. Extrae los commits del día, los agrupa por eje temático y los formatea con el template estándar.
---

## Cuándo usarse

Al final de cada sesión de trabajo en DocScan Studio, antes de hacer push final
o cerrar la conversación. La regla está en `CLAUDE.md` / memoria del proyecto:

> **OBLIGATORIO**: Al final de cada sesión, crear un documento de progreso en
> `docs/` con formato `docs/progreso_YYYY-MM-DD.md`.

## Pasos que ejecuta esta skill

### 1. Determinar la fecha
Usar la fecha actual (formato `YYYY-MM-DD`). El fichero resultante es
`docs/progreso_YYYY-MM-DD.md`. Si ya existe, preguntar al usuario antes de
sobreescribir.

### 2. Recolectar los commits de la sesión
Ejecutar:
```bash
git log --since="today 00:00" --pretty=format:"%h %s" --no-merges
```
O bien, si la sesión empezó antes de hoy:
```bash
git log BASE_REF..HEAD --pretty=format:"%h %s" --no-merges
```
donde `BASE_REF` es el último commit del informe anterior (mirar `docs/progreso_*.md`
más reciente para inferir el punto de partida).

Para cada commit, obtener el diff con `git show --stat HASH` para saber qué
ficheros tocó y estimar el alcance.

### 3. Extraer metadata clave
- **Rama actual**: `git rev-parse --abbrev-ref HEAD`
- **Nº de tests actual**: leer del último mensaje de commit que lo mencione, o
  ejecutar `pytest --co -q | tail -1` si es barato.
- **Nuevos endpoints/modelos/servicios**: `git diff --stat` filtrando por
  `web/api/routers/`, `app/services/`, `app/models/`, etc.

### 4. Agrupar cambios por eje temático
No listar commit a commit. Agrupar por **unidad funcional** (p.ej. "CRUD de
lotes", "upload de páginas", "fix de cleanup"). Un eje puede agrupar varios
commits.

### 5. Aplicar el template

```markdown
# Progreso YYYY-MM-DD — TÍTULO CORTO DE LA SESIÓN

## Resumen

Párrafo de 2-4 líneas explicando de qué fue la sesión. Mencionar la rama y el
contexto (continuación de X, inicio de Y).

## 1. Primer eje temático

Explicación narrativa, no lista de commits. El lector (el jefe) quiere entender
**qué se hizo y por qué**, no el detalle técnico.

### Endpoints / Archivos nuevos
(Solo si hay API nueva — tabla de rutas)

| Método | Ruta | Descripción |
|---|---|---|
| ... | ... | ... |

### Tests

Frase corta: "N tests nuevos cubriendo X, Y, Z."

Commit: **`HASH tipo: mensaje`**

## 2. Segundo eje temático

Misma estructura.

## Estado actual del proyecto

- **Rama**: `feature/xxx`, N commits por delante del remote (o sincronizado)
- **Tests totales**: **NNN passing**, 0 failures
- **Endpoints disponibles**: listado breve
- **Otras notas**: ...

## Decisiones tomadas

Bullets cortos explicando decisiones de diseño no obvias, con el "por qué".
Formato: **Decisión**: motivación.

## Próximos pasos (en orden)

1. Primer próximo paso concreto
2. Segundo
3. ...

## Archivos clave

- `ruta/a/fichero.py` — qué aporta
- ...
```

### 6. Tono y estilo

- **Lector objetivo**: el jefe del proyecto, que no vive en el código día a día.
- **Español de España** (castellano peninsular).
- **Narrativo, no lista de commits**. "Se añadió X para Y" mejor que "commit abc123: feat: X".
- **Enlazar commits** al final de cada sección con el hash corto y el subject.
- **No meter código fuente salvo snippets muy cortos** (1-3 líneas) que ilustren
  una decisión concreta.
- **Incluir métricas** cuando existan (nº tests, nº endpoints, líneas +/-).

### 7. Verificaciones finales antes de entregar

- El fichero existe en `docs/progreso_YYYY-MM-DD.md` con la fecha del día.
- El tono es profesional pero accesible.
- La sección "Próximos pasos" es específica y accionable, no genérica.
- Los hashes de commits mencionados son correctos (verificar con `git log`).
- Si hay un informe anterior (`docs/progreso_YYYY-MM-DD_previo.md`), la
  narrativa tiene continuidad (menciona "continuando desde la sesión de X").

### 8. Commitear el informe

Tras crear el fichero, añadirlo a git y crear un commit dedicado:
```bash
git add docs/progreso_YYYY-MM-DD.md
git commit -m "docs: progress report — título corto (YYYY-MM-DD)"
```

El informe va en su propio commit, separado de los commits de código.

## Ejemplo de referencia

Ver `docs/progreso_2026-04-07.md` y `docs/progreso_2026-04-09.md` como ejemplos
del tono, estructura y nivel de detalle esperados.
