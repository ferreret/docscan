"""Cola de tareas: abstrae enqueue ARQ vs ejecución inline en tests.

En producción (``settings.tasks.inline=False``) los jobs se enrolan a Redis
y un worker dedicado los procesa. En tests (``inline=True``, default) los
jobs se ejecutan en el mismo proceso del request, manteniendo el contrato
síncrono de FastAPI BackgroundTasks que asumen los tests existentes.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
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


async def enqueue_or_run(
    function_name: str,
    *args: Any,
    inline_kwargs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """Enrola un job a ARQ (producción) o lo ejecuta inline (tests).

    En modo inline:
    - Busca ``function_name`` en ``_INLINE_REGISTRY``.
    - Lo ejecuta con ``asyncio.to_thread`` para no bloquear el event loop
      (los runners son síncronos y pueden tardar minutos).
    - Inyecta ``inline_kwargs`` además de ``kwargs``.

    En modo ARQ:
    - Llama ``pool.enqueue_job(function_name, *args, **kwargs)``.
    - ``inline_kwargs`` se descarta: contiene objetos no serializables
      (p. ej. el ``BaseStorage`` que viene de DI). El handler ARQ del
      worker los reconstruye de su ``ctx`` (ver ``worker.py::pipeline_job``).

    Raises:
        KeyError: si ``inline=True`` y la función no está registrada.
    """
    settings = _get_settings()
    if settings.tasks.inline:
        if function_name not in _INLINE_REGISTRY:
            raise KeyError(f"Runner inline no registrado: {function_name!r}")
        func = _INLINE_REGISTRY[function_name]
        merged = {**kwargs, **(inline_kwargs or {})}
        await asyncio.to_thread(func, *args, **merged)
        return

    pool = await get_arq_pool()
    await pool.enqueue_job(function_name, *args, **kwargs)
