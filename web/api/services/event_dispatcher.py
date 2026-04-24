"""Ejecuta eventos lifecycle del workbench web en el backend.

Reutiliza el ScriptEngine del pipeline. Los scripts viven en
``application.events_json`` bajo la clave del nombre del evento.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.page_context import AppContext, BatchContext, PageContext
from app.services.script_engine import ScriptEngine

from web.api.schemas.event import EventResult

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

# Timeout usado al instanciar ScriptEngine (segundos).
# run_event no acepta timeout directamente; el timeout se aplica
# en run_step vía _execute_with_timeout. Para eventos de ciclo de
# vida el timeout se configura en el constructor.
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
    - Cualquier excepción del script se captura y devuelve
      ``EventResult(executed=True, error=str(e))``.
    - Las mutaciones de ``page.fields`` y ``batch.fields`` se persisten en BD.
    """
    script_source = _load_event_script(application, event_name)
    if not script_source:
        return EventResult(executed=False)

    engine = ScriptEngine(script_timeout=SCRIPT_TIMEOUT_SECONDS)
    try:
        engine.compile_script(event_name, script_source, event_name)
    except Exception as e:
        log.warning("Error compilando %s (app %d): %s", event_name, application.id, e)
        return EventResult(executed=True, error=f"compile error: {e}")

    app_ctx = _build_app_context(application)
    batch_ctx = _build_batch_context(batch)
    page_ctx = _build_page_context(page) if page else None

    kwargs: dict[str, Any] = {"app": app_ctx, "batch": batch_ctx}
    if page_ctx is not None:
        kwargs["page"] = page_ctx
    if key is not None:
        kwargs["key"] = key
    if extra:
        kwargs["extra"] = extra

    # run_event ya captura y loguea internamente las excepciones del script.
    # No acepta parámetro timeout — el timeout se aplica vía script_timeout
    # del constructor de ScriptEngine (solo afecta a run_step/run_pipeline).
    raw = engine.run_event(
        script_id=event_name,
        entry_point=event_name,
        **kwargs,
    )

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


def _build_app_context(application: Application) -> AppContext:
    return AppContext(
        id=application.id,
        name=application.name,
        description=application.description,
        output_format=application.output_format,
        auto_transfer=application.auto_transfer,
    )


def _build_batch_context(batch: Batch) -> BatchContext:
    try:
        fields = json.loads(batch.fields_json) if batch.fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    return BatchContext(
        id=batch.id,
        fields=fields,
        state=batch.state,
        page_count=batch.page_count,
        folder_path=batch.folder_path,
        hostname=batch.hostname,
    )


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
