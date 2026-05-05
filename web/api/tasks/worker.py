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
from arq.worker import func

from web.api import _register_models  # noqa: F401 — registra modelos SQLAlchemy
from web.api.config import get_web_settings
from web.api.storage import get_storage
from web.api.tasks.pipeline_runner import run_pipeline_for_batch as _pipeline_runner
from web.api.tasks.recovery import recover_stuck_batches
from web.api.tasks.transfer_runner import run_transfer_for_batch as _transfer_runner

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
    ctx["storage"] = get_storage()
    log.info(
        "Worker ARQ arrancado (storage backend=%s, queue=%s)",
        settings.storage.backend,
        settings.tasks.queue_name,
    )


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("Worker ARQ detenido")


# ----------------------------------------------------------------------
# Handlers
#
# Cada handler async se registra en ARQ con el mismo nombre que enrola el
# router (``run_pipeline_for_batch`` / ``run_transfer_for_batch``) usando
# ``arq.worker.func(name=...)``. Esto permite que el `_INLINE_REGISTRY` y
# el worker ARQ compartan el mismo nombre lógico.
# ----------------------------------------------------------------------


async def pipeline_job(ctx: dict[str, Any], batch_id: int) -> None:
    """Ejecuta el pipeline de un lote (handler ARQ)."""
    storage = ctx["storage"]
    log.info("Worker recibió pipeline_job para batch %d", batch_id)
    await asyncio.to_thread(_pipeline_runner, batch_id=batch_id, storage=storage)


async def transfer_job(ctx: dict[str, Any], batch_id: int) -> None:
    """Ejecuta la transferencia de un lote (handler ARQ)."""
    storage = ctx["storage"]
    log.info("Worker recibió transfer_job para batch %d", batch_id)
    await asyncio.to_thread(_transfer_runner, batch_id=batch_id, storage=storage)


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

    functions = [
        func(pipeline_job, name="run_pipeline_for_batch"),
        func(transfer_job, name="run_transfer_for_batch"),
        recovery_job,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    queue_name = get_web_settings().tasks.queue_name
    max_tries = get_web_settings().tasks.max_tries
    job_timeout = get_web_settings().tasks.job_timeout_seconds
    max_jobs = 4  # Concurrencia: 4 lotes simultáneos por worker
