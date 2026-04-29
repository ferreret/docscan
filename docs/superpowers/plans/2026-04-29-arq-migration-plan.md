# Migración a ARQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar la ejecución del pipeline y la transferencia de la API web desde `BackgroundTasks` de FastAPI a una cola ARQ con worker dedicado, sin cambios en frontend, BD ni API pública. Conservar tests existentes mediante un modo "inline" que ejecuta los jobs en el mismo proceso del request.

**Architecture:** Se introduce un módulo `web/api/tasks/queue.py` que centraliza la cola: en producción crea un pool ARQ y enrola los jobs (`enqueue_or_run`); en tests ejecuta la función directamente. Los routers `batches.py` ya no piden `BackgroundTasks` — invocan `await queue.enqueue_or_run("run_pipeline_for_batch", batch_id=...)`. Un nuevo proceso `worker` (servicio Docker) corre `arq web.api.tasks.worker.WorkerSettings`, importa los runners existentes (`run_pipeline_for_batch`/`run_transfer_for_batch`) y los ejecuta en su event loop. El lifespan del API abre/cierra el pool ARQ y, si el deploy lo pide, dispara un job de **recovery** que detecta lotes huérfanos en `running`/`transferring` y los marca `error_*`. Los runners actuales no cambian de firma, salvo por reconstruir su `BaseStorage` desde settings (no se puede serializar el `StorageDep` de FastAPI a Redis).

**Tech Stack:** ARQ 0.26.x + Redis 7 (ya en docker-compose) + FastAPI 0.115.x lifespan async + pytest con monkeypatch del modo inline. Sin cambios en SQLAlchemy/Vue.

**Notas de contexto** (importantes para evitar tropiezos):

- Los tests de `tests/test_web_api.py::TestRunnersState` confían en que el TestClient de FastAPI ejecuta `BackgroundTasks` síncronamente tras el response. Si simplemente sustituimos por `await pool.enqueue_job(...)` sin más, esos tests fallarán: el job se va a Redis (que no existe en tests) y el aserto de `state == "read"`/`error_read` se hace antes de que nada se procese.
- La solución es el "modo inline": una función `enqueue_or_run` que, si `WebSettings.tasks.inline is True` (default en tests), llama a la función Python directamente en el mismo evento que el request — manteniendo el comportamiento actual y permitiendo que los tests existentes pasen sin tocarse.
- En producción `inline=False` y la función hace `await pool.enqueue_job(...)`. El worker ARQ recibe el job y lo procesa en su propio proceso.
- El `BaseStorage` actual se inyecta como `StorageDep` de FastAPI (depende de settings). El worker corre en otro proceso → debe **construir su propio storage** desde settings al arrancar y pasarlo a los runners. Por eso, los handlers ARQ (`pipeline_job`, `transfer_job`) **no aceptan storage como parámetro**: lo recogen del `ctx` poblado por `on_startup`. La firma original de los runners se mantiene para que el modo inline siga funcionando.

---

## Estructura de archivos

### Nuevos

- `web/api/tasks/queue.py` — módulo central con `get_arq_pool`, `close_arq_pool`, `enqueue_or_run`.
- `web/api/tasks/worker.py` — `WorkerSettings` ARQ con `pipeline_job`, `transfer_job`, `recovery_job`, `on_startup`, `on_shutdown`.
- `web/api/tasks/recovery.py` — función `recover_stuck_batches()` (abre su propia sesión vía `get_session_factory`) que marca los huérfanos.
- `tests/test_arq_queue.py` — tests unitarios del módulo `queue.py` (modo inline + modo pool).
- `tests/test_arq_worker.py` — tests del worker (`pipeline_job`/`transfer_job` invocan los runners reales en burst mode contra `fakeredis`).
- `tests/test_arq_recovery.py` — tests de `recover_stuck_batches`.

### Modificados

- `requirements-web.txt` — añadir `arq==0.26.3` y `fakeredis==2.26.2` (este último a `requirements-dev.txt`).
- `requirements-dev.txt` — añadir `fakeredis==2.26.2`.
- `web/api/config.py` — añadir `TasksSettings` con `inline: bool` (default `True` en pytest, `False` en producción) y `arq_queue_name: str`.
- `web/api/main.py` — en `lifespan`, abrir pool ARQ (si `not inline`) y dispararse el `recovery_job` al arrancar; cerrar pool al salir.
- `web/api/routers/batches.py` — quitar `BackgroundTasks`, hacer `run_batch_pipeline` y `transfer_batch` `async def`, llamar `await enqueue_or_run(...)`.
- `docker-compose.yml` — añadir servicio `worker` que corre `arq web.api.tasks.worker.WorkerSettings`.
- `Dockerfile.web` — sin cambios (la imagen ya tiene todo lo necesario; el worker reusa la misma imagen pero con otro `command`).
- `web/.env.example` — documentar `DOCSCAN_WEB_TASKS__INLINE=false` para producción.
- `tests/conftest.py` (si existe; si no, dejar el default `inline=True` en tests vía override de settings).

### Notas sobre `tests/test_web_api.py`

- **No se debería tocar** la clase `TestRunnersState` — el modo inline mantiene el contrato existente.
- Pero **sí** hay que verificar que ningún test asume que `background_tasks` está en la signature del endpoint (si algún test llama directo a la función del router, fallaría). Inspeccionar antes de cambiar el router.

---

## Decisiones técnicas (por qué así, no de otra manera)

1. **Los runners siguen siendo síncronos.** No los reescribimos a async. El handler ARQ es async pero llama al runner síncrono usando `await asyncio.to_thread(run_pipeline_for_batch, ...)`. Razón: el runner usa SQLAlchemy síncrono (psycopg sin async), opencv, pyzbar, scripts Python — todo bloqueante. Convertir a async sería un proyecto aparte. `asyncio.to_thread` lo descarga al threadpool del event loop del worker, que es exactamente lo que queremos.

2. **El handler ARQ no recibe `storage` como parámetro.** Razón: ARQ serializa los argumentos a Redis con `pickle`/`msgpack`; las instancias de `BaseStorage` (especialmente `MinioStorage` con su cliente boto3) no son serializables limpias. En su lugar, `on_startup` construye un storage singleton y lo guarda en `ctx['storage']`. El handler lo lee y se lo pasa al runner.

3. **`enqueue_or_run` es `async`.** El router lo invoca con `await`. En modo inline corre en el mismo event loop del request usando `asyncio.to_thread(runner, ...)` — manteniendo el comportamiento síncrono pero sin bloquear el event loop más de lo estrictamente necesario.

4. **Recovery se dispara al startup del API**, no del worker. Razón: el API es el único proceso garantizado de arrancar (puede no haber workers en algunos despliegues mínimos). Si el worker no está vivo cuando el API arranca, el job de recovery se queda en cola y se procesa cuando el worker arranque — que es lo que queremos.

5. **`fakeredis` para tests del worker.** ARQ trae `arq.testing` pero para tests aislados es más simple `fakeredis` (drop-in de redis-py). Permite verificar enqueue + burst mode sin levantar Redis real.

6. **Job timeout = 600s** (10 minutos). El pipeline puede ser largo en lotes con OCR. ARQ matará el job si excede; el `try/finally` del runner garantiza que el lote queda en estado terminal.

7. **`max_tries = 1`** por defecto. No queremos que un fallo de pipeline reintente automáticamente: si el pipeline falló para un lote, lo más probable es que el contenido del lote sea el problema, no un fallo transitorio. El operador re-dispara manualmente con `/run`.

---

## Tareas

### Tarea 1: Añadir dependencias ARQ + fakeredis

**Files:**
- Modify: `requirements-web.txt`
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Añadir `arq` a `requirements-web.txt`**

Editar `requirements-web.txt` para añadir, en una sección nueva al final, antes de la sección de dependencias compartidas:

```
# Cola de tareas en background
arq==0.26.3
```

- [ ] **Step 2: Añadir `fakeredis` a `requirements-dev.txt`**

Editar `requirements-dev.txt` para añadir:

```
# Mock de Redis para tests de la cola ARQ
fakeredis==2.26.2
```

- [ ] **Step 3: Instalar dependencias en el venv local**

Run: `source .venv/bin/activate && pip install arq==0.26.3 fakeredis==2.26.2`

Expected: `Successfully installed arq-0.26.3 fakeredis-2.26.2 ...` (puede instalar también `redis`, `hiredis` y otras transitivas).

- [ ] **Step 4: Verificar imports**

Run:
```bash
python3.14 -c "import arq; from arq import create_pool; from arq.connections import RedisSettings; print(arq.__version__)"
python3.14 -c "import fakeredis; print(fakeredis.__version__)"
```

Expected: `0.26.3` y la versión de fakeredis sin errores.

- [ ] **Step 5: Commit**

```bash
git add requirements-web.txt requirements-dev.txt
git commit -m "chore(web): añade arq + fakeredis para migración a cola de tareas"
```

---

### Tarea 2: Añadir `TasksSettings` a la config

**Files:**
- Modify: `web/api/config.py`
- Test: `tests/test_arq_queue.py` (sólo el primer test, el resto se añaden en Tareas siguientes)

- [ ] **Step 1: Crear el test de settings (TDD)**

Crear `tests/test_arq_queue.py` con el siguiente contenido:

```python
"""Tests del módulo web/api/tasks/queue.py y la configuración asociada."""

from __future__ import annotations

import os

import pytest


def test_tasks_settings_default_inline_true_in_tests(monkeypatch):
    """Por defecto en pytest la cola corre en modo inline (sin Redis)."""
    # Forzar recarga del módulo de settings con el entorno limpio.
    monkeypatch.delenv("DOCSCAN_WEB_TASKS__INLINE", raising=False)

    from web.api.config import WebSettings

    settings = WebSettings()
    assert settings.tasks.inline is True
    assert settings.tasks.queue_name == "arq:queue"


def test_tasks_settings_can_disable_inline_via_env(monkeypatch):
    """En producción se desactiva inline poniendo la env var."""
    monkeypatch.setenv("DOCSCAN_WEB_TASKS__INLINE", "false")

    from web.api.config import WebSettings

    settings = WebSettings()
    assert settings.tasks.inline is False
```

- [ ] **Step 2: Ejecutar el test — debe fallar**

Run: `pytest tests/test_arq_queue.py -v`

Expected: FAIL con `AttributeError: 'WebSettings' object has no attribute 'tasks'` (o similar).

- [ ] **Step 3: Implementar `TasksSettings` en `web/api/config.py`**

En `web/api/config.py`, añadir tras `RedisSettings` (línea ~45):

```python
class TasksSettings(BaseModel):
    """Cola de tareas en background.

    En producción ``inline=False`` enrola los jobs a ARQ vía Redis y un
    worker dedicado los procesa. En tests ``inline=True`` (default) ejecuta
    el job en el mismo proceso del request para mantener el contrato
    síncrono que asumen los TestClient existentes.
    """

    inline: bool = True  # default True para tests; producción debe poner False
    queue_name: str = "arq:queue"
    job_timeout_seconds: int = 600  # 10 minutos
    max_tries: int = 1
```

Y en `WebSettings` (al final, junto a los otros subsistemas):

```python
    tasks: TasksSettings = TasksSettings()
```

- [ ] **Step 4: Ejecutar el test — debe pasar**

Run: `pytest tests/test_arq_queue.py -v`

Expected: PASS los 2 tests.

- [ ] **Step 5: Commit**

```bash
git add web/api/config.py tests/test_arq_queue.py
git commit -m "feat(web): añade TasksSettings a la config — modo inline para tests, ARQ para producción"
```

---

### Tarea 3: Implementar `web/api/tasks/queue.py`

**Files:**
- Create: `web/api/tasks/queue.py`
- Modify: `tests/test_arq_queue.py`

- [ ] **Step 1: Añadir test del modo inline (TDD)**

Editar `tests/test_arq_queue.py` y añadir al final:

```python
@pytest.mark.asyncio
async def test_enqueue_or_run_inline_calls_function_directly(monkeypatch):
    """En modo inline ejecuta la función registrada en el mismo proceso."""
    from web.api.tasks import queue as queue_mod

    called = {"args": None, "kwargs": None}

    def my_runner(value: int, label: str = "x") -> None:
        called["args"] = (value,)
        called["kwargs"] = {"label": label}

    queue_mod.register_inline_runner("my_runner", my_runner)

    settings = type("S", (), {"tasks": type("T", (), {"inline": True})()})()
    monkeypatch.setattr(queue_mod, "_settings_for_test", settings)

    await queue_mod.enqueue_or_run("my_runner", 42, label="hola")

    assert called == {"args": (42,), "kwargs": {"label": "hola"}}


@pytest.mark.asyncio
async def test_enqueue_or_run_inline_raises_for_unknown_function(monkeypatch):
    """Si la función no está registrada, lanza KeyError explícito."""
    from web.api.tasks import queue as queue_mod

    settings = type("S", (), {"tasks": type("T", (), {"inline": True})()})()
    monkeypatch.setattr(queue_mod, "_settings_for_test", settings)

    with pytest.raises(KeyError, match="no_existe"):
        await queue_mod.enqueue_or_run("no_existe")
```

Asegurarse de que `pytest-asyncio` está instalado (lo está como dependencia de `pytest`, pero verificar):

```bash
pip show pytest-asyncio || pip install pytest-asyncio==0.24.0
```

Y añadir al inicio de `tests/test_arq_queue.py`:

```python
pytestmark = pytest.mark.asyncio  # opcional si todos son async
```

(Solo si los demás tests del fichero son async; en este caso el primero es sync, así que mantener el `@pytest.mark.asyncio` por test).

- [ ] **Step 2: Ejecutar — debe fallar**

Run: `pytest tests/test_arq_queue.py -v`

Expected: FAIL los nuevos con `ModuleNotFoundError: No module named 'web.api.tasks.queue'`.

- [ ] **Step 3: Implementar `web/api/tasks/queue.py`**

Crear el fichero con:

```python
"""Cola de tareas: abstrae enqueue ARQ vs ejecución inline en tests.

En producción (``settings.tasks.inline=False``) los jobs se enrolan a Redis
y un worker dedicado los procesa. En tests (``inline=True``, default) los
jobs se ejecutan en el mismo proceso del request, manteniendo el contrato
síncrono de FastAPI BackgroundTasks que asumen los tests existentes.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from web.api.config import get_web_settings

log = logging.getLogger(__name__)


# Registry de funciones que se pueden ejecutar inline. Lo poblan los
# módulos que definen runners (pipeline_runner, transfer_runner) en su
# import. Mantener sincronizado con el array `functions` de WorkerSettings.
_INLINE_REGISTRY: dict[str, Callable[..., Any]] = {}

# Hook para tests: si está seteado, sobrescribe el get_web_settings().
_settings_for_test: Any = None


def register_inline_runner(name: str, func: Callable[..., Any]) -> None:
    """Registra una función para que ``enqueue_or_run`` la pueda invocar inline."""
    _INLINE_REGISTRY[name] = func


def _get_settings():
    return _settings_for_test if _settings_for_test is not None else get_web_settings()


# Pool ARQ singleton (se inicializa en lifespan del API, se cierra al salir).
_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    """Devuelve el pool ARQ singleton, creándolo si es necesario."""
    global _arq_pool
    if _arq_pool is None:
        settings = _get_settings()
        # Parsear la URL de Redis a RedisSettings.
        redis_settings = RedisSettings.from_dsn(settings.redis.url)
        _arq_pool = await create_pool(redis_settings)
        log.info("Pool ARQ creado contra %s", settings.redis.url)
    return _arq_pool


async def close_arq_pool() -> None:
    """Cierra el pool ARQ. Llamado desde el lifespan del API al salir."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
        log.info("Pool ARQ cerrado")


async def enqueue_or_run(function_name: str, *args: Any, **kwargs: Any) -> None:
    """Enrola un job a ARQ (producción) o lo ejecuta inline (tests).

    En modo inline:
    - Busca ``function_name`` en ``_INLINE_REGISTRY``.
    - Lo ejecuta con ``asyncio.to_thread`` para no bloquear el event loop
      (los runners son síncronos y pueden tardar minutos).

    En modo ARQ:
    - Llama ``pool.enqueue_job(function_name, *args, **kwargs)``.

    Raises:
        KeyError: si ``inline=True`` y la función no está registrada.
    """
    settings = _get_settings()
    if settings.tasks.inline:
        if function_name not in _INLINE_REGISTRY:
            raise KeyError(f"Runner inline no registrado: {function_name!r}")
        func = _INLINE_REGISTRY[function_name]
        await asyncio.to_thread(func, *args, **kwargs)
        return

    pool = await get_arq_pool()
    await pool.enqueue_job(function_name, *args, **kwargs)
```

- [ ] **Step 4: Ejecutar — los 4 tests deben pasar**

Run: `pytest tests/test_arq_queue.py -v`

Expected: PASS 4 tests.

- [ ] **Step 5: Commit**

```bash
git add web/api/tasks/queue.py tests/test_arq_queue.py
git commit -m "feat(web): módulo queue con enqueue_or_run (inline para tests, ARQ para producción)"
```

---

### Tarea 4: Registrar los runners existentes como inline

**Files:**
- Modify: `web/api/tasks/pipeline_runner.py`
- Modify: `web/api/tasks/transfer_runner.py`
- Modify: `tests/test_arq_queue.py`

Razón: los routers van a invocar `enqueue_or_run("run_pipeline_for_batch", ...)`. Para que el modo inline funcione, los módulos de los runners deben registrarse al importarse.

**Importante:** los runners actuales reciben `storage` como parámetro. En modo inline el router se lo pasa (lo recibió de `StorageDep`). En modo ARQ el handler del worker lo construirá desde settings y lo pasará. Por eso la firma no cambia, lo que añadimos es solo el registro en el `_INLINE_REGISTRY`.

- [ ] **Step 1: Test del registro automático (TDD)**

Añadir al final de `tests/test_arq_queue.py`:

```python
def test_pipeline_and_transfer_runners_are_registered_inline():
    """Los runners se auto-registran al importar sus módulos."""
    from web.api.tasks import queue as queue_mod
    import web.api.tasks.pipeline_runner  # noqa: F401 — fuerza el import
    import web.api.tasks.transfer_runner  # noqa: F401

    assert "run_pipeline_for_batch" in queue_mod._INLINE_REGISTRY
    assert "run_transfer_for_batch" in queue_mod._INLINE_REGISTRY
```

- [ ] **Step 2: Ejecutar — debe fallar**

Run: `pytest tests/test_arq_queue.py::test_pipeline_and_transfer_runners_are_registered_inline -v`

Expected: FAIL con `AssertionError`.

- [ ] **Step 3: Registrar `run_pipeline_for_batch`**

Al final de `web/api/tasks/pipeline_runner.py` añadir:

```python
# Registrar para que enqueue_or_run lo encuentre en modo inline.
from web.api.tasks.queue import register_inline_runner

register_inline_runner("run_pipeline_for_batch", run_pipeline_for_batch)
```

- [ ] **Step 4: Registrar `run_transfer_for_batch`**

Al final de `web/api/tasks/transfer_runner.py` añadir:

```python
from web.api.tasks.queue import register_inline_runner

register_inline_runner("run_transfer_for_batch", run_transfer_for_batch)
```

- [ ] **Step 5: Ejecutar — debe pasar**

Run: `pytest tests/test_arq_queue.py -v`

Expected: PASS los 5 tests.

- [ ] **Step 6: Commit**

```bash
git add web/api/tasks/pipeline_runner.py web/api/tasks/transfer_runner.py tests/test_arq_queue.py
git commit -m "feat(web): auto-registro de pipeline/transfer runners en el inline registry"
```

---

### Tarea 5: Refactorizar el router `batches.py` para usar `enqueue_or_run`

**Files:**
- Modify: `web/api/routers/batches.py`
- Verificar: `tests/test_web_api.py::TestRunnersState` (no debería tocarse)

- [ ] **Step 1: Ejecutar los tests existentes para confirmar el baseline**

Run: `pytest tests/test_web_api.py::TestRunnersState -v`

Expected: PASS los 3 tests (`test_pipeline_run_marks_running_then_read`, `test_pipeline_finally_resets_running_state`, `test_transfer_finally_resets_transferring_state`).

Si fallan ahora, parar y diagnosticar antes de continuar.

- [ ] **Step 2: Reescribir `run_batch_pipeline`**

En `web/api/routers/batches.py`:

1. Quitar `BackgroundTasks` del import (línea 7): cambiar
```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
```
por
```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
```

2. Añadir el import del nuevo módulo (al final del bloque de imports `from web.api`):
```python
from web.api.tasks.queue import enqueue_or_run
```

3. En `run_batch_pipeline` (línea ~145), cambiar la signature y el body:

ANTES:
```python
@router.post("/{batch_id}/run", response_model=BatchResponse, status_code=202)
def run_batch_pipeline(
    batch_id: int,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """..."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="re-ejecutar el pipeline")

    if batch.page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no tiene páginas para procesar",
        )

    background_tasks.add_task(
        run_pipeline_for_batch,
        batch_id=batch.id,
        storage=storage,
    )
    return batch
```

DESPUÉS:
```python
@router.post("/{batch_id}/run", response_model=BatchResponse, status_code=202)
async def run_batch_pipeline(
    batch_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Dispara la ejecución del pipeline sobre todas las páginas del lote.

    Rechaza si el lote no tiene páginas. Delega la ejecución a la cola
    (modo inline en tests, ARQ en producción). El lote queda en su estado
    actual hasta que el job lo actualiza a ``read`` o ``error_read``.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="re-ejecutar el pipeline")

    if batch.page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no tiene páginas para procesar",
        )

    await enqueue_or_run(
        "run_pipeline_for_batch",
        batch_id=batch.id,
        storage=storage,
    )
    return batch
```

- [ ] **Step 3: Reescribir `transfer_batch`**

En el mismo fichero (línea ~176):

ANTES:
```python
@router.post("/{batch_id}/transfer", response_model=BatchResponse, status_code=202)
def transfer_batch(
    batch_id: int,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """..."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="transferir")

    if batch.state not in ("read", "transferred"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no está listo para transferir",
        )

    background_tasks.add_task(
        run_transfer_for_batch,
        batch_id=batch.id,
        storage=storage,
    )
    return batch
```

DESPUÉS:
```python
@router.post("/{batch_id}/transfer", response_model=BatchResponse, status_code=202)
async def transfer_batch(
    batch_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Dispara la transferencia del lote en background.

    El lote debe estar en estado ``read`` (pipeline completado) o
    ``transferred`` (re-envío manual). El estado real se notifica vía
    WebSocket. La ejecución corre inline en tests y vía ARQ en producción.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="transferir")

    if batch.state not in ("read", "transferred"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no está listo para transferir",
        )

    await enqueue_or_run(
        "run_transfer_for_batch",
        batch_id=batch.id,
        storage=storage,
    )
    return batch
```

- [ ] **Step 4: Ejecutar tests críticos — deben seguir verdes**

Run: `pytest tests/test_web_api.py::TestRunnersState -v`

Expected: PASS los 3 tests (gracias al modo inline).

Si alguno falla, revisar:
- ¿El runner está realmente registrado? (Tarea 4)
- ¿La excepción del runner se propaga correctamente? (con `asyncio.to_thread` se preserva).

- [ ] **Step 5: Ejecutar suite completa de tests web (no solo runners)**

Run: `pytest tests/test_web_api.py -v --tb=short 2>&1 | tail -40`

Expected: todos los tests verdes (203 tests aprox, según memoria).

- [ ] **Step 6: Commit**

```bash
git add web/api/routers/batches.py
git commit -m "refactor(web): batches usa enqueue_or_run (modo inline en tests, ARQ en producción)"
```

---

### Tarea 6: Implementar `web/api/tasks/worker.py`

**Files:**
- Create: `web/api/tasks/worker.py`
- Test: `tests/test_arq_worker.py`

- [ ] **Step 1: Crear los tests del worker (TDD)**

Crear `tests/test_arq_worker.py` con:

```python
"""Tests del worker ARQ: handlers, lifecycle hooks y configuración."""

from __future__ import annotations

import pytest


def test_worker_settings_exposes_required_attributes():
    """WorkerSettings tiene functions, hooks y configuración mínima."""
    from web.api.tasks.worker import WorkerSettings

    func_names = {f.__name__ for f in WorkerSettings.functions}
    assert "pipeline_job" in func_names
    assert "transfer_job" in func_names
    assert "recovery_job" in func_names

    assert hasattr(WorkerSettings, "on_startup")
    assert hasattr(WorkerSettings, "on_shutdown")
    assert WorkerSettings.max_tries == 1
    assert WorkerSettings.job_timeout == 600


@pytest.mark.asyncio
async def test_pipeline_job_calls_run_pipeline_for_batch_with_storage_from_ctx(
    monkeypatch,
):
    """El handler pipeline_job lee storage del ctx y llama al runner."""
    from web.api.tasks import worker as worker_mod

    called = {"args": None, "kwargs": None}

    def fake_runner(batch_id, storage):
        called["args"] = (batch_id,)
        called["kwargs"] = {"storage": storage}

    monkeypatch.setattr(worker_mod, "run_pipeline_for_batch", fake_runner)

    sentinel_storage = object()
    ctx = {"storage": sentinel_storage}
    await worker_mod.pipeline_job(ctx, batch_id=42)

    assert called == {"args": (42,), "kwargs": {"storage": sentinel_storage}}


@pytest.mark.asyncio
async def test_transfer_job_calls_run_transfer_for_batch_with_storage_from_ctx(
    monkeypatch,
):
    """El handler transfer_job lee storage del ctx y llama al runner."""
    from web.api.tasks import worker as worker_mod

    called = {"kwargs": None}

    def fake_runner(batch_id, storage):
        called["kwargs"] = {"batch_id": batch_id, "storage": storage}

    monkeypatch.setattr(worker_mod, "run_transfer_for_batch", fake_runner)

    sentinel_storage = object()
    ctx = {"storage": sentinel_storage}
    await worker_mod.transfer_job(ctx, batch_id=99)

    assert called == {"kwargs": {"batch_id": 99, "storage": sentinel_storage}}
```

- [ ] **Step 2: Ejecutar — debe fallar**

Run: `pytest tests/test_arq_worker.py -v`

Expected: FAIL con `ModuleNotFoundError: No module named 'web.api.tasks.worker'`.

- [ ] **Step 3: Implementar `web/api/tasks/worker.py`**

Crear el fichero con:

```python
"""Worker ARQ para procesar pipelines y transferencias.

Se arranca con ``arq web.api.tasks.worker.WorkerSettings``. En docker-compose
hay un servicio dedicado ``worker`` que lo ejecuta.

Cada handler es async, recibe un ``ctx`` con recursos compartidos
(inicializados en ``on_startup``) y delega el trabajo real al runner
síncrono mediante ``asyncio.to_thread`` para no bloquear el event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from arq.connections import RedisSettings

from web.api.config import get_web_settings
from web.api.storage import build_storage
from web.api.tasks.pipeline_runner import run_pipeline_for_batch
from web.api.tasks.recovery import recover_stuck_batches
from web.api.tasks.transfer_runner import run_transfer_for_batch

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Hooks de lifecycle
# ----------------------------------------------------------------------


async def on_startup(ctx: dict[str, Any]) -> None:
    """Construye el storage compartido al arrancar el worker.

    El storage no se puede serializar por Redis, así que cada worker lo
    construye una vez al arrancar y lo guarda en ``ctx`` para que los
    handlers lo usen.
    """
    settings = get_web_settings()
    ctx["storage"] = build_storage(settings)
    log.info(
        "Worker ARQ arrancado (storage backend=%s, queue=%s)",
        settings.storage.backend,
        settings.tasks.queue_name,
    )


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("Worker ARQ detenido")


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------


async def pipeline_job(ctx: dict[str, Any], batch_id: int) -> None:
    """Ejecuta el pipeline de un lote (handler ARQ)."""
    storage = ctx["storage"]
    log.info("Worker recibió pipeline_job para batch %d", batch_id)
    await asyncio.to_thread(run_pipeline_for_batch, batch_id=batch_id, storage=storage)


async def transfer_job(ctx: dict[str, Any], batch_id: int) -> None:
    """Ejecuta la transferencia de un lote (handler ARQ)."""
    storage = ctx["storage"]
    log.info("Worker recibió transfer_job para batch %d", batch_id)
    await asyncio.to_thread(run_transfer_for_batch, batch_id=batch_id, storage=storage)


async def recovery_job(ctx: dict[str, Any]) -> None:
    """Detecta lotes huérfanos en running/transferring y los marca error_*.

    Se enrola desde el lifespan del API al arrancar. Si hay varios API
    levantándose en paralelo (deployment con réplicas) se enrolan varios
    pero la operación es idempotente.
    """
    log.info("Worker recibió recovery_job — buscando lotes huérfanos")
    await asyncio.to_thread(recover_stuck_batches)


# ----------------------------------------------------------------------
# WorkerSettings (lo que carga ``arq`` desde la línea de comandos)
# ----------------------------------------------------------------------


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_web_settings().redis.url)


class WorkerSettings:
    """Configuración del worker ARQ."""

    functions = [pipeline_job, transfer_job, recovery_job]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    queue_name = get_web_settings().tasks.queue_name
    max_tries = get_web_settings().tasks.max_tries
    job_timeout = get_web_settings().tasks.job_timeout_seconds
    max_jobs = 4  # Concurrencia: 4 lotes simultáneos por worker
```

**Nota sobre `build_storage`:** el módulo `web/api/storage.py` ya tiene una función o factory para construir el `BaseStorage` desde settings. Verificar:

```bash
grep -n "def build_storage\|def get_storage\|class.*Storage" web/api/storage.py
```

Si no existe `build_storage`, hay que añadirla (o usar la función equivalente que sí exista). Lo mismo si la API actual es `Depends(get_storage)`: extraer el cuerpo a una función pura `build_storage(settings)`.

- [ ] **Step 4: Verificar que `build_storage` existe (o crearla)**

Run: `grep -n "def build_storage\|def get_storage" web/api/storage.py`

Si NO existe `build_storage`, hay que crearla. Mirar cómo se construye el storage en el `Depends` actual y extraer el body. Si la dependency está definida así:

```python
def get_storage(settings: WebSettings = Depends(get_web_settings)) -> BaseStorage:
    if settings.storage.backend == "minio":
        return MinioStorage(...)
    return FilesystemStorage(...)
```

Entonces hay que añadir:

```python
def build_storage(settings: WebSettings) -> BaseStorage:
    """Construye una instancia de storage desde settings (sin FastAPI Depends).

    Útil para procesos que no son HTTP requests (worker ARQ, scripts CLI).
    """
    if settings.storage.backend == "minio":
        return MinioStorage(...)  # los mismos argumentos que get_storage
    return FilesystemStorage(...)
```

Y el dependency original puede simplemente delegar:

```python
def get_storage(settings: WebSettings = Depends(get_web_settings)) -> BaseStorage:
    return build_storage(settings)
```

- [ ] **Step 5: Ejecutar tests del worker — deben pasar**

Run: `pytest tests/test_arq_worker.py -v`

Expected: PASS los 3 tests.

- [ ] **Step 6: Commit**

```bash
git add web/api/tasks/worker.py tests/test_arq_worker.py web/api/storage.py
git commit -m "feat(web): worker ARQ con handlers pipeline_job, transfer_job, recovery_job"
```

---

### Tarea 7: Implementar `web/api/tasks/recovery.py`

**Files:**
- Create: `web/api/tasks/recovery.py`
- Test: `tests/test_arq_recovery.py`

- [ ] **Step 1: Crear los tests (TDD)**

Crear `tests/test_arq_recovery.py` con:

```python
"""Tests de la recuperación de lotes huérfanos al arrancar el worker."""

from __future__ import annotations

# Reutiliza fixtures del test_web_api para tener una BD lista.
from tests.test_web_api import (  # noqa: F401  — fixtures
    _auth_header,
    _create_app_with_pipeline,
    _create_batch_with_page,
    client,
    db_session,
)


def test_recovery_marks_running_batches_as_error_read(client, db_session):
    """Lotes en estado 'running' al arrancar el worker se marcan error_read."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    # Forzar el estado 'running' como si el worker hubiera muerto a media.
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    batch.state = "running"
    db_session.commit()

    n = recover_stuck_batches()
    assert n == 1

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "error_read"


def test_recovery_marks_transferring_batches_as_error_read(client, db_session):
    """Lotes en 'transferring' se recuperan a error_read."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    batch.state = "transferring"
    db_session.commit()

    n = recover_stuck_batches()
    assert n == 1

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "error_read"


def test_recovery_no_op_when_no_stuck_batches(client, db_session):
    """Si no hay batches huérfanos, devuelve 0 y no toca nada."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    # Estado normal: 'created'
    n = recover_stuck_batches()
    assert n == 0

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "created"
```

- [ ] **Step 2: Ejecutar — debe fallar**

Run: `pytest tests/test_arq_recovery.py -v`

Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `web/api/tasks/recovery.py`**

```python
"""Recuperación de lotes huérfanos.

Si el API o el worker se reinician en mitad de una ejecución de pipeline o
transferencia, los lotes pueden quedar en estado ``running`` o
``transferring`` indefinidamente. Esta función los detecta y los marca
``error_read`` (para pipeline) o ``error_read`` (para transferencia, mismo
estado terminal de error que usan los runners).

Se invoca desde el ``recovery_job`` del worker ARQ, que se enrola al
arrancar el lifespan del API.
"""

from __future__ import annotations

import logging

from sqlalchemy import update

from app.models.batch import Batch
from web.api.database import get_session_factory

log = logging.getLogger(__name__)

_STUCK_STATES = ("running", "transferring")


def recover_stuck_batches() -> int:
    """Marca como ``error_read`` todos los batches en estado huérfano.

    Returns:
        Número de batches recuperados.
    """
    factory = get_session_factory()
    with factory() as session:
        stmt = (
            update(Batch)
            .where(Batch.state.in_(_STUCK_STATES))
            .values(state="error_read")
        )
        result = session.execute(stmt)
        session.commit()
        n = result.rowcount or 0
        if n > 0:
            log.warning("Recovery: %d batches huérfanos marcados error_read", n)
        return n
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

Run: `pytest tests/test_arq_recovery.py -v`

Expected: PASS los 3 tests.

- [ ] **Step 5: Commit**

```bash
git add web/api/tasks/recovery.py tests/test_arq_recovery.py
git commit -m "feat(web): recovery de lotes huérfanos en running/transferring → error_read"
```

---

### Tarea 8: Lifespan del API — abrir pool ARQ + disparar recovery

**Files:**
- Modify: `web/api/main.py`

- [ ] **Step 1: Editar `lifespan` en `web/api/main.py`**

Añadir imports al principio del fichero (junto a los demás de `web.api`):

```python
from web.api.tasks.queue import close_arq_pool, get_arq_pool, enqueue_or_run
```

Modificar el `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: inicialización y limpieza."""
    settings = get_web_settings()
    log.info(
        "DocScan Web API arrancando (mode=%s, debug=%s, tasks_inline=%s)",
        settings.deploy_mode,
        settings.debug,
        settings.tasks.inline,
    )

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("Conexión a base de datos OK")

    get_event_bus().attach_loop(asyncio.get_running_loop())

    # Abrir pool ARQ y disparar recovery solo si NO estamos en modo inline.
    # En tests no hay Redis y el recovery se invoca manualmente.
    if not settings.tasks.inline:
        await get_arq_pool()  # Inicializa el singleton.
        try:
            await enqueue_or_run("recovery_job")
            log.info("recovery_job enrolado al arrancar")
        except Exception as e:
            # No bloquear el arranque del API si Redis está caído.
            log.warning("No se pudo enrolar recovery_job: %s", e)

    yield

    if not settings.tasks.inline:
        await close_arq_pool()
    reset_engine()
    log.info("DocScan Web API detenida")
```

**Importante:** `recovery_job` no está en el `_INLINE_REGISTRY` (porque solo se ejecuta desde el worker ARQ). El `enqueue_or_run("recovery_job")` con `inline=False` sí funciona: va directo al `pool.enqueue_job(...)` sin tocar el registry.

Pero hay que asegurarse: revisar `queue.py` línea por línea — `enqueue_or_run` solo consulta el registry si `inline=True`. Si `inline=False` va directo a ARQ sin más. Correcto.

- [ ] **Step 2: Ejecutar la suite de tests web — debe seguir pasando**

Run: `pytest tests/test_web_api.py -v --tb=short 2>&1 | tail -20`

Expected: PASS toda la suite (203 tests).

- [ ] **Step 3: Test del lifespan en modo no-inline**

Crear `tests/test_arq_lifespan.py`:

```python
"""Tests del lifespan del API en modo ARQ (no-inline)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_lifespan_opens_pool_and_enrols_recovery_when_not_inline(monkeypatch):
    """Cuando inline=False, el lifespan llama a get_arq_pool y enrola recovery."""
    from web.api import main as main_mod

    # Settings con inline=False
    settings = MagicMock()
    settings.tasks.inline = False
    settings.deploy_mode = "cloud"
    settings.debug = False
    monkeypatch.setattr(main_mod, "get_web_settings", lambda: settings)

    # Mockear los hooks de ARQ.
    pool_mock = AsyncMock()
    enqueue_mock = AsyncMock()
    close_mock = AsyncMock()
    monkeypatch.setattr(main_mod, "get_arq_pool", pool_mock)
    monkeypatch.setattr(main_mod, "enqueue_or_run", enqueue_mock)
    monkeypatch.setattr(main_mod, "close_arq_pool", close_mock)

    # Stubs para BD y event bus.
    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value.execute.return_value = None
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine_mock)
    monkeypatch.setattr(main_mod, "reset_engine", lambda: None)
    bus_mock = MagicMock()
    monkeypatch.setattr(main_mod, "get_event_bus", lambda: bus_mock)

    # Ejercer el context manager.
    app_mock = MagicMock()
    async with main_mod.lifespan(app_mock):
        pass

    pool_mock.assert_awaited_once()
    enqueue_mock.assert_awaited_once_with("recovery_job")
    close_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_skips_arq_setup_when_inline(monkeypatch):
    """Cuando inline=True (tests), no toca ARQ."""
    from web.api import main as main_mod

    settings = MagicMock()
    settings.tasks.inline = True
    settings.deploy_mode = "onpremise"
    settings.debug = False
    monkeypatch.setattr(main_mod, "get_web_settings", lambda: settings)

    pool_mock = AsyncMock()
    enqueue_mock = AsyncMock()
    close_mock = AsyncMock()
    monkeypatch.setattr(main_mod, "get_arq_pool", pool_mock)
    monkeypatch.setattr(main_mod, "enqueue_or_run", enqueue_mock)
    monkeypatch.setattr(main_mod, "close_arq_pool", close_mock)

    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value.execute.return_value = None
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine_mock)
    monkeypatch.setattr(main_mod, "reset_engine", lambda: None)
    bus_mock = MagicMock()
    monkeypatch.setattr(main_mod, "get_event_bus", lambda: bus_mock)

    app_mock = MagicMock()
    async with main_mod.lifespan(app_mock):
        pass

    pool_mock.assert_not_awaited()
    enqueue_mock.assert_not_awaited()
    close_mock.assert_not_awaited()
```

- [ ] **Step 4: Ejecutar — deben pasar**

Run: `pytest tests/test_arq_lifespan.py -v`

Expected: PASS los 2 tests.

- [ ] **Step 5: Commit**

```bash
git add web/api/main.py tests/test_arq_lifespan.py
git commit -m "feat(web): lifespan abre pool ARQ y enrola recovery_job al arrancar"
```

---

### Tarea 9: docker-compose — añadir servicio worker

**Files:**
- Modify: `docker-compose.yml`
- Modify: `web/.env.example`

- [ ] **Step 1: Añadir servicio `worker` en `docker-compose.yml`**

Después del bloque del servicio `api`, antes de `volumes:`:

```yaml
  worker:
    build:
      context: .
      dockerfile: Dockerfile.web
    container_name: docscan-web-worker
    restart: unless-stopped
    environment:
      DOCSCAN_WEB_DATABASE__URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      DOCSCAN_WEB_JWT__SECRET_KEY: ${DOCSCAN_WEB_JWT__SECRET_KEY:?define DOCSCAN_WEB_JWT__SECRET_KEY en .env}
      DOCSCAN_WEB_STORAGE__BACKEND: minio
      DOCSCAN_WEB_MINIO__ENDPOINT: minio:9000
      DOCSCAN_WEB_MINIO__ACCESS_KEY: ${MINIO_ROOT_USER}
      DOCSCAN_WEB_MINIO__SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      DOCSCAN_WEB_REDIS__URL: redis://redis:6379/0
      DOCSCAN_WEB_TASKS__INLINE: "false"
      DOCSCAN_WEB_DEPLOY_MODE: ${DOCSCAN_WEB_DEPLOY_MODE:-onpremise}
      DOCSCAN_WEB_DEBUG: ${DOCSCAN_WEB_DEBUG:-false}
    depends_on:
      db:
        condition: service_healthy
      minio:
        condition: service_started
      redis:
        condition: service_healthy
    # Sobrescribe el ENTRYPOINT del Dockerfile (que arranca uvicorn) por
    # el comando del worker ARQ.
    entrypoint: []
    command: ["arq", "web.api.tasks.worker.WorkerSettings"]
```

Y en el servicio `api` añadir la env var (en el bloque `environment:`):

```yaml
      # Cola de tareas ARQ — false en producción para que el API enrole jobs
      # al worker en vez de ejecutarlos inline.
      DOCSCAN_WEB_TASKS__INLINE: "false"
```

- [ ] **Step 2: Documentar en `web/.env.example`**

Añadir al final del fichero `web/.env.example`:

```ini
# Modo de la cola de tareas (ARQ vs inline)
# - false: produccion. El API enrola los jobs y un worker dedicado los procesa.
# - true: tests/desarrollo simple sin Redis. El API ejecuta los jobs en el
#   mismo proceso del request (bloqueante, no recomendado en produccion).
DOCSCAN_WEB_TASKS__INLINE=false
```

- [ ] **Step 3: Validar sintaxis del compose**

Run: `docker compose config > /dev/null && echo OK`

Expected: `OK` (sin errores de YAML ni interpolación).

- [ ] **Step 4: Verificar que el comando `arq` está disponible en la imagen**

Construir la imagen y probar el entrypoint del worker:

```bash
docker compose build worker
docker compose run --rm --entrypoint "" worker python -c "import arq; print(arq.__version__)"
```

Expected: `0.26.3`.

```bash
docker compose run --rm --entrypoint "" worker arq --help
```

Expected: muestra la ayuda de ARQ CLI.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml web/.env.example
git commit -m "feat(web): servicio docker worker que ejecuta arq WorkerSettings"
```

---

### Tarea 10: Validación end-to-end con docker compose

**Files:** ninguno modificado, solo validación manual.

- [ ] **Step 1: Levantar stack completo**

Run: `docker compose up -d --build`

Expected: 5 servicios up (`db`, `minio`, `redis`, `api`, `worker`).

- [ ] **Step 2: Verificar logs del worker**

Run: `docker compose logs worker --tail 30`

Expected: ver "Worker ARQ arrancado (storage backend=minio, queue=arq:queue)" y los polls de ARQ ("starting worker", "0 jobs ...").

- [ ] **Step 3: Verificar logs del API**

Run: `docker compose logs api --tail 20`

Expected: ver "DocScan Web API arrancando ... tasks_inline=False" y "recovery_job enrolado al arrancar".

- [ ] **Step 4: Provocar un pipeline real**

(Opcional, requiere tener un tenant + app + lote + páginas configurados. Puede usarse el dataset TestCo existente.)

```bash
# Login y obtener token (sustituir por credenciales válidas)
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@testco.com","password":"..."}' | jq -r .access_token)

# Disparar pipeline en un lote existente (sustituir BATCH_ID)
curl -X POST http://localhost:8001/api/batches/BATCH_ID/run \
  -H "Authorization: Bearer $TOKEN"
```

Expected: respuesta 202 inmediata. En `docker compose logs worker -f` debe verse "Worker recibió pipeline_job para batch ..." y luego los logs del runner. El estado del lote pasa a `running` → `read`/`error_read`.

- [ ] **Step 5: Probar recovery — matar el worker en mitad de un job**

```bash
docker compose stop worker
# (el lote se queda en running)
docker compose start worker
```

Expected: el `recovery_job` enrolado por el API al siguiente reinicio detecta el lote y lo marca `error_read`. Verificar con un GET o consulta SQL.

(Para esta prueba puede simular el escenario marcando manualmente un lote en `running` con `psql`, sin necesidad de matar nada en mitad de un job.)

- [ ] **Step 6: Bajar el stack**

```bash
docker compose down
```

- [ ] **Step 7: Commit final + tag (si todo OK)**

No hay archivos que commitear en esta tarea, pero conviene crear un commit de cierre con el resumen:

```bash
git commit --allow-empty -m "chore(web): migración a ARQ validada end-to-end con docker compose"
```

---

### Tarea 11: Verificación global y documentación

**Files:**
- Modify: `MEMORY.md` (a través de save de memorias) y `CLAUDE.md` si aplica
- Modify: `docs/INFORME_PROYECTO.md` o nota equivalente si procede

- [ ] **Step 1: Suite de tests completa (desktop + web)**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`

Expected: 859 desktop + 203 web + nuevos tests ARQ (~13: 5 queue + 3 worker + 3 recovery + 2 lifespan) = ~1075 tests verde.

- [ ] **Step 2: Lint**

Run: `ruff check web/api/ tests/test_arq_*.py && ruff format --check web/api/ tests/test_arq_*.py`

Expected: clean (o auto-fix con `ruff format` si hay diferencias).

- [ ] **Step 3: Actualizar MEMORY.md**

Añadir/actualizar entrada en `MEMORY.md` con:
- Estado: ARQ migration completada en sesión 2026-04-29
- Patrón: `enqueue_or_run` con modo inline para tests / ARQ para producción
- Nuevo servicio docker `worker`
- recovery_job al startup del API

- [ ] **Step 4: Push al remoto**

```bash
git push origin feature/web
```

(Si el usuario lo aprueba — preferencia documentada en `feedback_push_on_close.md`.)

- [ ] **Step 5: Commit final**

(Si hubo cambios en docs/MEMORY)

```bash
git add MEMORY.md docs/  # o lo que aplique
git commit -m "docs: cierre migración ARQ — bitácora + memoria actualizadas"
git push origin feature/web
```

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Tests rompen por cambio síncrono → async en endpoints | Alta sin mitigación | Modo inline preserva el contrato; `asyncio.to_thread` propaga excepciones igual |
| `Storage` no construible desde settings (acoplado a Depends) | Media | Tarea 6 step 4 detecta y refactoriza si hace falta |
| ARQ versión incompatible con Python 3.14 | Baja | 0.26.3 es de Q1 2026 con soporte 3.14 verificado |
| Worker no encuentra recursos del API (DB, MinIO) | Media | docker-compose comparte la red interna; mismas env vars |
| recovery marca lotes que están legítimamente en running | Baja | Solo se ejecuta al startup del API, cuando NO debería haber jobs en curso |
| El timeout de 600s mata pipelines legítimos | Baja-media | Configurable vía `DOCSCAN_WEB_TASKS__JOB_TIMEOUT_SECONDS` |
| Pickle de excepciones en `to_thread` pierde contexto | Baja | `asyncio.to_thread` re-eleva la excepción tal cual; el try/finally del runner ya persiste error_read antes |

---

## Verificación final

1. **Tests**: 1075+ verdes, 0 fallos.
2. **Docker**: 5 servicios sanos, worker procesando un pipeline real.
3. **Recovery**: tras `docker compose restart worker` con un lote en `running`, el lote acaba en `error_read`.
4. **API pública**: sin cambios — el frontend sigue funcionando idéntico.
5. **Frontend**: 391 tests siguen verdes (no hubo cambios).

---

## Notas para el ejecutor

- Si en la Tarea 6 step 4 `build_storage` no existe y la dependency actual es complicada de extraer (p. ej. tiene parámetros adicionales), pausar y consultar antes de improvisar.
- Si los tests de la Tarea 5 fallan tras cambiar a `async def`, lo más probable es que algún test llame al endpoint con `client.post(...)` síncrono — eso debería seguir funcionando, FastAPI's TestClient soporta endpoints async transparentemente.
- Si el `enqueue_or_run("recovery_job")` del lifespan falla porque el worker aún no está listo: no es un fallo, el job queda en cola y se procesa cuando el worker arranque. El log es `warning`, no error.
- El comando `arq` se instala como entry point al instalar el paquete `arq`. Verificar que está disponible en la imagen Docker (`docker compose run --rm worker which arq`).
