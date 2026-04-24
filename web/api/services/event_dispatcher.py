"""Ejecuta eventos lifecycle del workbench web en el backend.

Reutiliza el ScriptEngine del pipeline. Los scripts viven en
``application.events_json`` bajo la clave del nombre del evento.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.page_context import PageContext
from app.services.script_engine import ScriptEngine

from web.api.schemas.event import EventResult
from web.api.services.context_builders import build_app_context, build_batch_context

log = logging.getLogger(__name__)

# Eventos lifecycle soportados por el endpoint web en Fase 4.
SUPPORTED_EVENTS = frozenset(
    {
        "on_batch_loaded",
        "on_navigate_prev",
        "on_navigate_next",
        "on_page_changed",
        "on_key_event",
    }
)

# Eventos que requieren page_id en el payload.
EVENTS_REQUIRING_PAGE_ID = frozenset(
    {
        "on_navigate_prev",
        "on_navigate_next",
        "on_page_changed",
    }
)

# Timeout para ejecución de scripts de evento (segundos).
# Se aplica en el dispatcher con ThreadPoolExecutor, no en ScriptEngine,
# porque run_event_raw propaga excepciones y no aplica timeout propio.
SCRIPT_TIMEOUT_SECONDS = 5


def dispatch_event(
    *,
    event_name: str,
    application: Application,
    batch: Batch,
    page: Page | None,
    key: str | None,
    extra: dict[str, Any],
    session: Session,
) -> EventResult:
    """Ejecuta el script asociado al evento y devuelve el resultado tipado.

    - Si el script no está definido en ``events_json`` devuelve
      ``EventResult(executed=False)``.
    - Un retorno ``False`` del script equivale a ``cancel=True``.
    - Un retorno ``dict`` se mapea a ``EventResult`` campo a campo
      (``cancel``, ``target_page_id``, ``fields_updated``, ``batch_fields_updated``,
      ``logs``, ``result``).
    - Cualquier excepción del script (incluido timeout >5s) se captura y devuelve
      ``EventResult(executed=True, error=str(e))``.
    - Las mutaciones de ``page.fields`` y ``batch.fields`` se persisten en BD.
    """
    script_source = _load_event_script(application, event_name)
    if not script_source:
        return EventResult(executed=False)

    engine = ScriptEngine()
    try:
        try:
            engine.compile_script(event_name, script_source, event_name)
        except Exception as e:
            log.warning(
                "Error compilando %s (app %d): %s", event_name, application.id, e
            )
            return EventResult(executed=True, error=f"compile error: {e}")

        app_ctx = build_app_context(application)
        batch_ctx = build_batch_context(batch)
        page_ctx = _build_page_context(page) if page else None

        kwargs: dict[str, Any] = {"app": app_ctx, "batch": batch_ctx}
        if page_ctx is not None:
            kwargs["page"] = page_ctx
        if key is not None:
            kwargs["key"] = key
        if extra:
            kwargs["extra"] = extra

        # Usamos run_event_raw (no traga excepciones) + ThreadPoolExecutor propio
        # para enforzar el timeout de 5s.  Si el script se cuelga o lanza,
        # devolvemos EventResult(executed=True, error=...) en lugar de None opaco.
        raw = _run_with_timeout(engine, event_name, kwargs)
        if isinstance(raw, EventResult):
            # _run_with_timeout devuelve EventResult solo en caso de error/timeout
            return raw

        result = _map_return_to_event_result(raw)

        if page is not None and page_ctx is not None and page_ctx.fields:
            result.fields_updated = page_ctx.fields.copy()
            page.index_fields_json = json.dumps(page_ctx.fields, ensure_ascii=False)
            session.add(page)

        if batch_ctx.fields:
            result.batch_fields_updated = batch_ctx.fields.copy()
            batch.fields_json = json.dumps(batch_ctx.fields, ensure_ascii=False)
            session.add(batch)

        if result.fields_updated or result.batch_fields_updated:
            session.commit()

        return result
    finally:
        engine.shutdown()


def _run_with_timeout(
    engine: ScriptEngine,
    event_name: str,
    kwargs: dict[str, Any],
) -> Any:
    """Ejecuta ``engine.run_event_raw`` con timeout de ``SCRIPT_TIMEOUT_SECONDS``.

    Usa un ``ThreadPoolExecutor`` de un hilo dedicado para que el timeout sea
    real (el hilo del worker FastAPI no queda bloqueado indefinidamente).

    Returns:
        El valor devuelto por el script en caso de éxito.
        Un ``EventResult(executed=True, error=...)`` si el script excede el
        timeout o lanza cualquier excepción.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            engine.run_event_raw,
            event_name,
            event_name,
            **kwargs,
        )
        try:
            return future.result(timeout=SCRIPT_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            log.error(
                "Evento '%s' excedió el timeout de %ds",
                event_name,
                SCRIPT_TIMEOUT_SECONDS,
            )
            future.cancel()
            return EventResult(executed=True, error="timeout")
        except Exception as e:  # noqa: BLE001
            log.error("Error ejecutando evento '%s': %s", event_name, e)
            return EventResult(executed=True, error=str(e))


def _load_event_script(application: Application, event_name: str) -> str | None:
    """Devuelve el código fuente del evento o None si no está definido."""
    try:
        events = json.loads(application.events_json or "{}")
    except json.JSONDecodeError:
        return None
    script = events.get(event_name)
    if not script or not script.strip():
        return None
    return script


def _build_page_context(page: Page) -> PageContext:
    try:
        fields = json.loads(page.index_fields_json) if page.index_fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    ctx = PageContext(page_index=page.page_index, image=None)
    ctx.fields = fields
    return ctx


def _map_return_to_event_result(raw: Any) -> EventResult:
    """Convierte el retorno del script en EventResult."""
    if raw is None or raw is True:
        return EventResult(executed=True)
    if raw is False:
        return EventResult(executed=True, cancel=True)
    if isinstance(raw, dict):
        return EventResult(
            executed=True,
            result=raw.get("result"),
            cancel=bool(raw.get("cancel", False)),
            target_page_id=raw.get("target_page_id"),
            fields_updated=dict(raw.get("fields_updated") or {}),
            batch_fields_updated=dict(raw.get("batch_fields_updated") or {}),
            logs=list(raw.get("logs") or []),
        )
    return EventResult(executed=True, result=raw)
