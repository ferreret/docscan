---
name: web-api-patterns
description: Convenciones obligatorias para la API web FastAPI de DocScan Studio (web/api/). Usar al implementar cualquier router, schema, dependency, storage o test de la web.
---

## Regla fundamental: tenant scoping

Todo endpoint autenticado DEBE filtrar por `user.tenant_id`. Un solo endpoint que
olvide hacerlo rompe el aislamiento multi-tenant.

```python
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.routers._helpers import get_batch_for_tenant

@router.get("/{batch_id}")
def get_batch(batch_id: int, user: CurrentUser, db: SessionDep):
    # OBLIGATORIO: filtrar por user.tenant_id
    return get_batch_for_tenant(batch_id, user.tenant_id, db)
```

## Helpers compartidos en `_helpers.py`

Si una función de lookup `get_xxx_or_404` se usa en más de un router, va en
`web/api/routers/_helpers.py`. No duplicar `select(Model).where(Model.tenant_id == ...)`
en cada router.

Ya existe `get_batch_for_tenant(batch_id, tenant_id, db) -> Batch`. Si necesitas
un lookup similar para otro recurso, añádelo al mismo fichero con la misma
firma (`id, tenant_id, db`).

## Validación de FKs cruzadas

Al crear un recurso hijo (batch dentro de app, page dentro de batch), SIEMPRE
validar que el padre pertenece al tenant del usuario. Patrón:

```python
def _assert_application_in_tenant(
    application_id: int, tenant_id: int, db: Session,
) -> None:
    app = db.execute(
        select(Application.id).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Aplicación no encontrada")
```

Usar 404 (no 403) para no filtrar la existencia del recurso ajeno.

## Storage cleanup al borrar en cascada

**Lección aprendida (smoke test 2026-04-09)**: la cascada ORM borra registros
Page pero deja los ficheros en disco huérfanos. Cualquier `DELETE` que elimine
en cascada debe:

1. Recoger los `image_path` ANTES del `db.delete(parent)`
2. Hacer el `db.commit()`
3. Iterar los paths y llamar `storage.delete(path)` tras el commit

```python
@router.delete("/{batch_id}", status_code=204)
def delete_batch(
    batch_id: int, user: CurrentUser, db: SessionDep, storage: StorageDep,
):
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    image_paths = [p.image_path for p in batch.pages if p.image_path]
    db.delete(batch)
    db.commit()
    for path in image_paths:
        storage.delete(path)
```

Para `delete_application` el patrón es igual pero con doble comprehension
(`for batch in app.batches for page in batch.pages`).

## Schemas Pydantic

- Si hay >5 campos compartidos entre Create/Response, extraer `_XxxBase`.
- Si hay validación contra constantes del modelo (p.ej. `BATCH_STATES`),
  usar `field_validator` importando el símbolo desde `app.models`. NO
  duplicar la lista de valores en el schema.
- `model_config = {"from_attributes": True}` obligatorio en schemas que se
  construyen desde instancias ORM.

## Storage filesystem

- Abstracción en `web/api/storage.py` (`FilesystemStorage`). Pensada para
  migrarse a MinIO/S3 sin tocar routers.
- Layout: `{base_path}/{tenant_id}/{batch_id}/{uuid}.{ext}`. El UUID evita
  colisiones entre páginas del mismo batch.
- `save()` crea el directorio si no existe. `delete()` usa `unlink(missing_ok=True)`
  para evitar TOCTOU y stats innecesarios.
- Inyectar siempre con `StorageDep`, nunca instanciar directo en el router.

## Tests

- Usar `storage_dir` fixture (ya definida en `tests/test_web_api.py`) cuando
  necesites asertar el estado del filesystem tras un delete.
- Override de dependencias de BD y storage vía `app.dependency_overrides`,
  NO monkey-patch de módulos.
- Helper `_auth_header(client, email=..., tenant_name=...)` ya existe para
  registrar usuario + obtener JWT en un solo paso.
- Helper `_create_app_and_get_id()` y `_create_batch()` para scaffolding.
- Helper `_make_png_bytes()` y `_make_pdf_bytes(num_pages=N)` para uploads.

## Subida multipart

- `list[UploadFile] = File(...)` en la firma del endpoint (no `Annotated[..., ...]`).
- Validar extensión contra whitelist explícita (`_SINGLE_IMAGE_EXTS`, `_PDF_EXTS`).
- Para PDFs: usar `_iter_pdf_pages_as_png()` (generador) que libera memoria
  página a página — NO acumular todas las páginas PNG en una lista.
- Actualizar `batch.page_count` en el mismo commit que los inserts de Page.

## PostgreSQL específico

- `render_as_batch=True` en Alembic para compatibilidad con SQLite en tests.
- `server_default=func.now()` en timestamps, NO default Python.
- Columnas nullable en migraciones ALTER: dar `server_default` o el NOT NULL
  fallará en SQLite.

## No hacer

- ❌ `db.query(...)` estilo SQLAlchemy 1.x. Usar `db.execute(select(...))`.
- ❌ `Session` global. Usar siempre `SessionDep` via context manager.
- ❌ 403 cuando el recurso no es del tenant. Usar 404 (no leakear existencia).
- ❌ `print()`. Usar `logging` stdlib.
- ❌ Hardcodear credenciales en defaults de config (ver commit 16f7f2d).
