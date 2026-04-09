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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.barcode import Barcode
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.executor import PipelineExecutor
from app.pipeline.page_context import (
    AppContext,
    BatchContext,
    PageContext,
)
from app.pipeline.serializer import deserialize
from app.services.barcode_service import BarcodeService
from app.services.image_pipeline import ImagePipelineService
from app.services.ocr_service import OcrService
from app.services.script_engine import ScriptEngine
from web.api.database import get_session_factory
from web.api.storage import FilesystemStorage

log = logging.getLogger(__name__)


def run_pipeline_for_batch(
    batch_id: int,
    storage: FilesystemStorage,
) -> None:
    """Ejecuta el pipeline de la aplicación sobre todas las páginas del lote.

    Pensada para invocarse como BackgroundTask de FastAPI. Es síncrona,
    abre su propia session de BD a través del singleton de session factory
    y captura todas las excepciones para registrar el estado final del lote
    (``read`` o ``error_read``).

    Args:
        batch_id: ID del lote a procesar.
        storage: Instancia de FilesystemStorage para cargar las imágenes.
    """
    factory = get_session_factory()
    with factory() as session:
        batch = session.get(Batch, batch_id)
        if batch is None:
            log.warning("Batch %d no encontrado para ejecución de pipeline", batch_id)
            return

        application = session.get(Application, batch.application_id)
        if application is None:
            log.error("Aplicación %d no encontrada", batch.application_id)
            batch.state = "error_read"
            session.commit()
            return

        try:
            executor = _build_executor(application)
        except Exception as e:
            log.exception("Error preparando executor: %s", e)
            batch.state = "error_read"
            session.commit()
            return

        app_ctx = _build_app_context(application)
        batch_ctx = _build_batch_context(batch)

        pages = (
            session.execute(
                select(Page).where(Page.batch_id == batch_id).order_by(Page.page_index)
            )
            .scalars()
            .all()
        )

        any_error = False
        for page in pages:
            try:
                _process_page(page, executor, app_ctx, batch_ctx, storage, session)
            except Exception as e:
                log.exception("Error procesando página %d: %s", page.id, e)
                any_error = True
                _record_processing_error(page, str(e))

        batch.state = "error_read" if any_error else "read"
        batch.page_count = len(pages)
        session.commit()
        log.info(
            "Pipeline completado para batch %d: %d páginas, estado=%s",
            batch_id,
            len(pages),
            batch.state,
        )


# ----------------------------------------------------------------------
# Helpers privados
# ----------------------------------------------------------------------


def _build_executor(application: Application) -> PipelineExecutor:
    """Construye un PipelineExecutor a partir del JSON de la aplicación."""
    steps = deserialize(application.pipeline_json)

    script_engine = ScriptEngine()
    for step in steps:
        if step.type == "script":
            try:
                script_engine.compile_step(step)
            except Exception as e:
                log.warning("Error compilando script '%s': %s", step.id, e)

    return PipelineExecutor(
        steps=steps,
        image_service=ImagePipelineService(),
        script_engine=script_engine,
        barcode_service=BarcodeService(),
        ocr_service=OcrService(),
    )


def _build_app_context(application: Application) -> AppContext:
    """Mapea Application ORM → AppContext del pipeline."""
    return AppContext(
        id=application.id,
        name=application.name,
        description=application.description,
        output_format=application.output_format,
        auto_transfer=application.auto_transfer,
    )


def _build_batch_context(batch: Batch) -> BatchContext:
    """Mapea Batch ORM → BatchContext del pipeline."""
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


def _process_page(
    page: Page,
    executor: PipelineExecutor,
    app_ctx: AppContext,
    batch_ctx: BatchContext,
    storage: FilesystemStorage,
    session: Session,
) -> None:
    """Carga la imagen, ejecuta el pipeline y persiste los resultados."""
    image = _load_image(page, storage)
    page_ctx = PageContext(page_index=page.page_index, image=image)

    executor.execute(page=page_ctx, batch=batch_ctx, app=app_ctx)

    _persist_page_results(page, page_ctx, session)


def _load_image(page: Page, storage: FilesystemStorage) -> Any:
    """Carga la imagen del page como ndarray BGR (formato esperado por el pipeline)."""
    if not page.image_path:
        raise FileNotFoundError(f"Page {page.id} no tiene image_path")
    abs_path = storage.absolute_path(page.image_path)
    image = cv2.imread(str(abs_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"No se pudo leer imagen: {abs_path}")
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


def _record_processing_error(page: Page, message: str) -> None:
    """Añade un error de procesado al campo JSON del page."""
    try:
        errors = json.loads(page.processing_errors_json or "[]")
    except json.JSONDecodeError:
        errors = []
    errors.append(message)
    page.processing_errors_json = json.dumps(errors, ensure_ascii=False)
    page.pipeline_processed = False
