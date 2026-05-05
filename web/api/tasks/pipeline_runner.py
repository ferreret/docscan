"""Background runner del pipeline para la API web.

Envuelve PipelineExecutor del desktop y lo orquesta para procesar todas
las páginas de un lote: carga la imagen desde storage, ejecuta el pipeline,
persiste los resultados (barcodes, ocr_text, fields, flags) y actualiza el
estado del lote.

Diseñado para ejecutarse como BackgroundTask de FastAPI: NO depende de Qt
ni de la SessionDep del request — abre su propia session via la factory
singleton del módulo de database.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.barcode import Barcode
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.executor import PipelineExecutor
from app.pipeline.page_context import (
    PageContext,
)
from app.pipeline.serializer import deserialize
from app.services.barcode_service import BarcodeService
from app.services.image_pipeline import ImagePipelineService
from app.services.ocr_service import OcrService
from app.services.script_engine import ScriptCompilationError, ScriptEngine

from web.api.database import get_session_factory
from web.api.events import PipelineEvent, PipelineEventBus, get_event_bus
from web.api.services.context_builders import build_app_context, build_batch_context
from web.api.storage import BaseStorage

log = logging.getLogger(__name__)


def run_pipeline_for_batch(
    batch_id: int,
    storage: BaseStorage,
    event_bus: PipelineEventBus | None = None,
) -> None:
    """Ejecuta el pipeline de la aplicación sobre todas las páginas del lote.

    Pensada para invocarse como BackgroundTask de FastAPI. Es síncrona,
    abre su propia session de BD a través del singleton de session factory.

    Marca el lote como ``running`` al empezar y garantiza un estado
    terminal (``read`` o ``error_read``) al salir mediante ``try/finally``.
    Si algo deja el lote colgado en ``running``, el finally lo fuerza a
    ``error_read``.

    Args:
        batch_id: ID del lote a procesar.
        storage: Instancia de BaseStorage para cargar las imágenes.
        event_bus: Bus opcional para publicar eventos de progreso. Si es
            ``None`` se usa el singleton por defecto.
    """
    bus = event_bus if event_bus is not None else get_event_bus()

    def emit(event_type: str, **payload: Any) -> None:
        bus.publish_from_thread(
            PipelineEvent(batch_id=batch_id, type=event_type, payload=payload)
        )

    factory = get_session_factory()
    with factory() as session:
        batch = session.get(Batch, batch_id)
        if batch is None:
            log.warning("Batch %d no encontrado para ejecución de pipeline", batch_id)
            emit("pipeline_error", error="batch_not_found")
            return

        # Marcar como running antes de cualquier trabajo pesado.
        batch.state = "running"
        session.commit()

        try:
            _execute_pipeline(batch_id, storage, session, emit)
        except Exception:
            log.exception("Pipeline falló para batch %d", batch_id)
            session.rollback()
            batch = session.get(Batch, batch_id)
            if batch is not None:
                batch.state = "error_read"
                session.commit()
            raise
        finally:
            # Garantía de estado terminal: si algo dejó el state en
            # "running", forzar error_read. Rollback previo porque la
            # session puede estar en estado sucio tras una excepción.
            session.rollback()
            batch = session.get(Batch, batch_id)
            if batch is not None and batch.state == "running":
                batch.state = "error_read"
                session.commit()


def _execute_pipeline(
    batch_id: int,
    storage: BaseStorage,
    session: Session,
    emit: Any,
) -> None:
    """Ejecuta el cuerpo del pipeline para todas las páginas del lote.

    Asume que ``batch.state`` ya está marcado como ``running`` y que el
    caller gestiona el try/finally de limpieza. Al terminar correctamente,
    deja ``batch.state`` en ``read`` o ``error_read`` según si alguna
    página falló.
    """
    batch = session.get(Batch, batch_id)
    if batch is None:
        # El caller ya comprobó esto, pero defendemos por si se llama directamente.
        log.warning("Batch %d desapareció durante la ejecución", batch_id)
        return

    application = session.get(Application, batch.application_id)
    if application is None:
        log.error("Aplicación %d no encontrada", batch.application_id)
        batch.state = "error_read"
        session.commit()
        emit("pipeline_error", error="application_not_found")
        return

    try:
        executor, pipeline_engine = build_executor(application)
    except Exception as e:
        log.exception("Error preparando executor: %s", e)
        batch.state = "error_read"
        session.commit()
        emit("pipeline_error", error=str(e))
        return

    try:
        app_ctx = build_app_context(application)
        batch_ctx = build_batch_context(batch)

        pages = (
            session.execute(
                select(Page).where(Page.batch_id == batch_id).order_by(Page.page_index)
            )
            .scalars()
            .all()
        )

        total = len(pages)
        emit("pipeline_started", total_pages=total)

        any_error = False
        for idx, page in enumerate(pages, start=1):
            try:
                process_page(page, executor, app_ctx, batch_ctx, storage, session)
                emit(
                    "page_processed",
                    page_id=page.id,
                    page_index=page.page_index,
                    processed=idx,
                    total=total,
                    ok=True,
                )
            except Exception as e:
                log.exception("Error procesando página %d: %s", page.id, e)
                any_error = True
                _record_processing_error(page, str(e))
                emit(
                    "page_processed",
                    page_id=page.id,
                    page_index=page.page_index,
                    processed=idx,
                    total=total,
                    ok=False,
                    error=str(e),
                )

        batch.state = "error_read" if any_error else "read"
        batch.page_count = total
        session.commit()
        log.info(
            "Pipeline completado para batch %d: %d páginas, estado=%s",
            batch_id,
            total,
            batch.state,
        )

        # on_scan_complete se dispara tras commit y antes de notificar al WebSocket.
        final_batch_ctx = build_batch_context(batch)
        _fire_scan_complete(application, app_ctx, final_batch_ctx)

        emit(
            "pipeline_completed",
            total_pages=total,
            state=batch.state,
            any_error=any_error,
        )
    finally:
        pipeline_engine.shutdown()


# ----------------------------------------------------------------------
# Helpers privados
# ----------------------------------------------------------------------


def build_executor(
    application: Application,
) -> tuple[PipelineExecutor, ScriptEngine]:
    """Construye un PipelineExecutor y devuelve su ScriptEngine asociado.

    El caller es responsable de llamar a script_engine.shutdown() cuando
    termine el procesamiento para liberar el ThreadPoolExecutor interno.
    """
    steps = deserialize(application.pipeline_json)

    script_engine = ScriptEngine()
    for step in steps:
        if step.type == "script":
            try:
                script_engine.compile_step(step)
            except Exception as e:
                log.warning("Error compilando script '%s': %s", step.id, e)

    executor = PipelineExecutor(
        steps=steps,
        image_service=ImagePipelineService(),
        script_engine=script_engine,
        barcode_service=BarcodeService(),
        ocr_service=OcrService(),
    )
    return executor, script_engine


def process_page(
    page: Page,
    executor: PipelineExecutor,
    app_ctx: Any,
    batch_ctx: Any,
    storage: BaseStorage,
    session: Session,
) -> None:
    """Carga la imagen, ejecuta el pipeline y persiste los resultados."""
    image = _load_image(page, storage)
    page_ctx = PageContext(page_index=page.page_index, id=page.id, image=image)

    executor.execute(page=page_ctx, batch=batch_ctx, app=app_ctx)

    _persist_page_results(page, page_ctx, session)


def _load_image(page: Page, storage: BaseStorage) -> Any:
    """Carga la imagen del page como ndarray BGR (formato esperado por el pipeline)."""
    if not page.image_path:
        raise FileNotFoundError(f"Page {page.id} no tiene image_path")
    raw = storage.read(page.image_path)
    arr = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"No se pudo decodificar imagen: {page.image_path}")
    return image


def _persist_page_results(
    page: Page,
    page_ctx: PageContext,
    session: Session,
) -> None:
    """Vuelca el contenido de PageContext al modelo Page (en la session)."""
    page.ocr_text = page_ctx.ocr_text or ""
    page.index_fields_json = json.dumps(page_ctx.fields, ensure_ascii=False)
    page.needs_review = page_ctx.flags.needs_review
    page.review_reason = page_ctx.flags.review_reason
    page.processing_errors_json = json.dumps(
        page_ctx.flags.processing_errors,
        ensure_ascii=False,
    )
    page.script_errors_json = json.dumps(
        page_ctx.flags.script_errors,
        ensure_ascii=False,
    )
    page.pipeline_processed = True

    # Reemplazar barcodes (limpiar previos y crear nuevos)
    for old in list(page.barcodes):
        session.delete(old)
    for bc in page_ctx.barcodes:
        session.add(
            Barcode(
                page_id=page.id,
                value=bc.value,
                symbology=bc.symbology,
                engine=bc.engine,
                step_id=bc.step_id,
                quality=bc.quality,
                pos_x=bc.pos_x,
                pos_y=bc.pos_y,
                pos_w=bc.pos_w,
                pos_h=bc.pos_h,
                role=bc.role,
            )
        )


def _fire_scan_complete(
    application: Application,
    app_ctx: Any,
    batch_ctx: Any,
) -> None:
    """Ejecuta on_scan_complete si está definido. Errores logueados como warning.

    Ordering invariant: llamar TRAS session.commit() y ANTES del emit
    pipeline_completed — así el script ve el estado final del lote y los
    subscriptores del WebSocket reciben la señal cuando todo el trabajo ha
    terminado (incluido este evento).
    """
    try:
        events = json.loads(application.events_json or "{}")
        if not isinstance(events, dict):
            return
    except json.JSONDecodeError:
        log.warning(
            "events_json inválido en app %d, no se dispara on_scan_complete",
            application.id,
        )
        return

    script = events.get("on_scan_complete")
    if not script or not script.strip():
        return

    engine = ScriptEngine()
    try:
        engine.compile_script("on_scan_complete", script, "on_scan_complete")
        engine.run_event(
            "on_scan_complete",
            "on_scan_complete",
            app=app_ctx,
            batch=batch_ctx,
        )
    except ScriptCompilationError as e:
        log.warning(
            "Error compilando on_scan_complete (app %d): %s",
            application.id,
            e,
        )
    except Exception as e:
        log.warning(
            "Error ejecutando on_scan_complete (app %d): %s",
            application.id,
            e,
        )
    finally:
        engine.shutdown()


def _record_processing_error(page: Page, message: str) -> None:
    """Añade un error de procesado al campo JSON del page."""
    try:
        errors = json.loads(page.processing_errors_json or "[]")
    except json.JSONDecodeError:
        errors = []
    errors.append(message)
    page.processing_errors_json = json.dumps(errors, ensure_ascii=False)
    page.pipeline_processed = False


# Registrar para que enqueue_or_run lo encuentre en modo inline.
from web.api.tasks.queue import register_inline_runner  # noqa: E402

register_inline_runner("run_pipeline_for_batch", run_pipeline_for_batch)
