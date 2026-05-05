"""Background runner de la transferencia para la API web.

Envuelve TransferService del desktop y lo orquesta para transferir todas
las páginas de un lote a su destino configurado: descarga las imágenes
desde storage a un directorio temporal, ejecuta on_transfer_validate
(que puede cancelar), invoca el servicio de transferencia, dispara
on_transfer_page por cada página y on_transfer_advanced al terminar.

Diseñado para ejecutarse como BackgroundTask de FastAPI: NO depende de
Qt ni de la SessionDep del request — abre su propia session via la
factory singleton del módulo de database.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.page_context import (
    AppContext,
    BatchContext,
    PageContext,
)
from app.services.script_engine import ScriptCompilationError, ScriptEngine
from app.services.transfer_service import (
    TransferResult,
    TransferService,
    parse_transfer_config,
)
from web.api.database import get_session_factory
from web.api.events import PipelineEvent, PipelineEventBus, get_event_bus
from web.api.storage import BaseStorage

log = logging.getLogger(__name__)


def run_transfer_for_batch(
    batch_id: int,
    storage: BaseStorage,
    event_bus: PipelineEventBus | None = None,
    transfer_service: TransferService | None = None,
) -> None:
    """Ejecuta la transferencia del lote.

    Pensada para invocarse como BackgroundTask de FastAPI. Es síncrona,
    abre su propia session de BD a través del singleton de session
    factory.

    Marca el lote como ``transferring`` al empezar y garantiza un estado
    terminal (``read`` o ``error_read``) al salir mediante ``try/finally``.
    Si algo deja el lote colgado en ``transferring``, el finally lo
    fuerza a ``error_read``.

    Args:
        batch_id: ID del lote a transferir.
        storage: Instancia de BaseStorage para cargar las imágenes.
        event_bus: Bus opcional para publicar eventos. Si es ``None`` se
            usa el singleton por defecto.
        transfer_service: Servicio de transferencia. Si es ``None`` se
            crea uno nuevo (inyectable para tests).
    """
    bus = event_bus if event_bus is not None else get_event_bus()
    service = transfer_service if transfer_service is not None else TransferService()

    def emit(event_type: str, **payload: Any) -> None:
        bus.publish_from_thread(
            PipelineEvent(batch_id=batch_id, type=event_type, payload=payload)
        )

    factory = get_session_factory()
    with factory() as session:
        batch = session.get(Batch, batch_id)
        if batch is None:
            log.warning("Batch %d no encontrado para transferencia", batch_id)
            emit("transfer_error", error="batch_not_found")
            return

        # Guardar el estado previo para poder restaurarlo si la
        # transferencia aborta por validación (no es un error).
        previous_state = batch.state
        batch.state = "transferring"
        session.commit()

        try:
            _execute_transfer(batch_id, storage, service, session, emit)
        except Exception:
            log.exception("Transfer falló para batch %d", batch_id)
            session.rollback()
            batch = session.get(Batch, batch_id)
            if batch is not None:
                batch.state = "error_read"
                session.commit()
            emit("transfer_error", error="unexpected_exception")
            raise
        finally:
            # Garantía de estado terminal: si algo dejó el state en
            # "transferring", forzar error_read. Rollback previo porque
            # la session puede estar en estado sucio tras una excepción.
            session.rollback()
            batch = session.get(Batch, batch_id)
            if batch is not None and batch.state == "transferring":
                # Si la transferencia abortó antes de empezar (ej. no
                # configurada), restauramos el estado previo en vez de
                # marcar error. El _execute_transfer ya debería haber
                # restaurado el estado, pero defendemos aquí.
                batch.state = (
                    previous_state if previous_state != "transferring" else "error_read"
                )
                session.commit()


def _execute_transfer(
    batch_id: int,
    storage: BaseStorage,
    service: TransferService,
    session: Session,
    emit: Any,
) -> None:
    """Ejecuta el cuerpo de la transferencia para el lote.

    Asume que ``batch.state`` ya está marcado como ``transferring`` y que
    el caller gestiona el try/finally de limpieza. Al terminar
    correctamente, deja ``batch.state`` en ``read``.

    Si la transferencia aborta por configuración inválida o por
    ``on_transfer_validate``, restaura el estado a ``read`` (el lote
    sigue siendo válido para reintentar).
    """
    batch = session.get(Batch, batch_id)
    if batch is None:
        log.warning("Batch %d desapareció durante la transferencia", batch_id)
        return

    application = session.get(Application, batch.application_id)
    if application is None:
        log.error("Aplicación %d no encontrada", batch.application_id)
        batch.state = "error_read"
        session.commit()
        emit("transfer_error", error="application_not_found")
        return

    # 1. Parsear configuración
    try:
        config = parse_transfer_config(application.transfer_json or "{}")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        log.warning(
            "transfer_json inválido en app %d: %s",
            application.id,
            e,
        )
        batch.state = "read"
        session.commit()
        emit("transfer_aborted", reason="not_configured")
        return

    if not config.standard_enabled:
        batch.state = "read"
        session.commit()
        emit("transfer_aborted", reason="not_configured")
        return

    if not config.destination:
        batch.state = "read"
        session.commit()
        emit("transfer_aborted", reason="not_configured")
        return

    # 2. Construir contextos para los firers
    app_ctx = _build_app_context(application)
    batch_ctx = _build_batch_context(batch)

    # 3. on_transfer_validate puede cancelar
    validate_result = _fire_transfer_validate(
        application,
        app_ctx,
        batch_ctx,
    )
    if validate_result is False:
        log.info(
            "Transferencia cancelada por on_transfer_validate en batch %d",
            batch_id,
        )
        batch.state = "read"
        session.commit()
        emit("transfer_aborted", reason="validate_returned_false")
        return

    # 4. Cargar páginas y batch_fields
    pages_orm = (
        session.execute(
            select(Page).where(Page.batch_id == batch_id).order_by(Page.page_index)
        )
        .scalars()
        .all()
    )
    total = len(pages_orm)
    try:
        batch_fields = json.loads(batch.fields_json) if batch.fields_json else {}
    except json.JSONDecodeError:
        batch_fields = {}

    emit("transfer_started", total_pages=total, mode=config.mode)

    # 5. Bajar imágenes a tempdir + transferir
    with tempfile.TemporaryDirectory(prefix="docscan_xfer_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        pages_payload = _materialize_pages(
            pages_orm,
            storage,
            tmpdir_path,
        )

        def on_page(page_index: int, success: bool) -> None:
            emit(
                "transfer_page",
                page_index=page_index,
                success=success,
            )
            page_orm = next(
                (p for p in pages_orm if p.page_index == page_index),
                None,
            )
            page_ctx = _build_page_context(page_orm)
            _fire_transfer_page(
                application,
                app_ctx,
                batch_ctx,
                page_ctx,
                success=success,
            )

        try:
            result = service.transfer(
                pages=pages_payload,
                config=config,
                batch_fields=batch_fields,
                batch_id=batch_id,
                on_page_callback=on_page,
            )
        except Exception as e:
            log.exception("Error en TransferService: %s", e)
            batch.state = "error_read"
            session.commit()
            emit("transfer_error", error=str(e))
            return

    # 6. on_transfer_advanced (post-procesado)
    _fire_transfer_advanced(
        application,
        app_ctx,
        batch_ctx,
        result,
    )

    # 7. Estado terminal en éxito: pasa a "transferred" para que el operador
    # vea claramente que el lote ya está enviado al destino. El endpoint de
    # transferir permite re-disparar desde "read" o "transferred" (el
    # operador puede querer reenviar si el destino externo perdió ficheros).
    batch.state = "transferred"
    session.commit()

    # 8. Notificar éxito final
    emit(
        "transfer_completed",
        success=result.success,
        output_path=result.output_path,
        files_transferred=result.files_transferred,
        errors=list(result.errors),
    )
    log.info(
        "Transferencia completada para batch %d: %d ficheros (success=%s)",
        batch_id,
        result.files_transferred,
        result.success,
    )


# ----------------------------------------------------------------------
# Helpers privados
# ----------------------------------------------------------------------


def _build_app_context(application: Application) -> AppContext:
    """Mapea Application ORM → AppContext para los scripts de eventos."""
    try:
        transfer_cfg = (
            json.loads(application.transfer_json) if application.transfer_json else {}
        )
    except json.JSONDecodeError:
        transfer_cfg = {}
    return AppContext(
        id=application.id,
        name=application.name,
        description=application.description,
        output_format=application.output_format,
        auto_transfer=application.auto_transfer,
        transfer_config=transfer_cfg,
    )


def _build_batch_context(batch: Batch) -> BatchContext:
    """Mapea Batch ORM → BatchContext para los scripts de eventos."""
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


def _build_page_context(page: Page | None) -> PageContext | None:
    """Construye un PageContext mínimo a partir de un Page ORM."""
    if page is None:
        return None
    try:
        fields = json.loads(page.index_fields_json) if page.index_fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    ctx = PageContext(page_index=page.page_index, id=page.id)
    ctx.ocr_text = page.ocr_text or ""
    ctx.fields = fields
    return ctx


def _materialize_pages(
    pages_orm: list[Page],
    storage: BaseStorage,
    tmpdir: Path,
) -> list[dict[str, Any]]:
    """Descarga las imágenes del storage al tempdir y construye la lista
    de dicts que espera ``TransferService.transfer``.

    Si una página no tiene image_path o el storage falla, se omite (se
    registrará como error en el resultado del transfer cuando la página
    no exista).
    """
    payload: list[dict[str, Any]] = []
    for page in pages_orm:
        if not page.image_path:
            continue
        try:
            content = storage.read(page.image_path)
        except FileNotFoundError:
            log.warning("Imagen no encontrada en storage: %s", page.image_path)
            continue

        ext = PurePosixPath(page.image_path).suffix or ".bin"
        local_path = tmpdir / f"page_{page.page_index:04d}{ext}"
        local_path.write_bytes(content)

        try:
            fields = (
                json.loads(page.index_fields_json) if page.index_fields_json else {}
            )
        except json.JSONDecodeError:
            fields = {}

        payload.append(
            {
                "image_path": str(local_path),
                "page_index": page.page_index,
                "fields": fields,
                "ocr_text": page.ocr_text or "",
            }
        )
    return payload


def _load_event_script(application: Application, event_name: str) -> str | None:
    """Devuelve el código fuente del evento o None si no está definido."""
    try:
        events = json.loads(application.events_json or "{}")
        if not isinstance(events, dict):
            return None
    except json.JSONDecodeError:
        log.warning(
            "events_json inválido en app %d, no se dispara %s",
            application.id,
            event_name,
        )
        return None
    script = events.get(event_name)
    if not script or not script.strip():
        return None
    return script


def _fire_transfer_validate(
    application: Application,
    app_ctx: AppContext,
    batch_ctx: BatchContext,
) -> Any:
    """Ejecuta on_transfer_validate si está definido.

    Returns:
        El valor retornado por el script (puede ser ``False`` para
        cancelar la transferencia). Si no hay script o falla, devuelve
        ``None`` (no cancela).
    """
    script = _load_event_script(application, "on_transfer_validate")
    if script is None:
        return None

    engine = ScriptEngine()
    try:
        engine.compile_script(
            "on_transfer_validate",
            script,
            "on_transfer_validate",
        )
        return engine.run_event(
            "on_transfer_validate",
            "on_transfer_validate",
            app=app_ctx,
            batch=batch_ctx,
        )
    except ScriptCompilationError as e:
        log.warning(
            "Error compilando on_transfer_validate (app %d): %s",
            application.id,
            e,
        )
        return None
    except Exception as e:
        log.warning(
            "Error ejecutando on_transfer_validate (app %d): %s",
            application.id,
            e,
        )
        return None
    finally:
        engine.shutdown()


def _fire_transfer_page(
    application: Application,
    app_ctx: AppContext,
    batch_ctx: BatchContext,
    page_ctx: PageContext | None,
    success: bool,
) -> None:
    """Ejecuta on_transfer_page si está definido. Errores logueados."""
    script = _load_event_script(application, "on_transfer_page")
    if script is None:
        return

    engine = ScriptEngine()
    try:
        engine.compile_script(
            "on_transfer_page",
            script,
            "on_transfer_page",
        )
        engine.run_event(
            "on_transfer_page",
            "on_transfer_page",
            app=app_ctx,
            batch=batch_ctx,
            page=page_ctx,
            result={"success": success},
        )
    except ScriptCompilationError as e:
        log.warning(
            "Error compilando on_transfer_page (app %d): %s",
            application.id,
            e,
        )
    except Exception as e:
        log.warning(
            "Error ejecutando on_transfer_page (app %d): %s",
            application.id,
            e,
        )
    finally:
        engine.shutdown()


def _fire_transfer_advanced(
    application: Application,
    app_ctx: AppContext,
    batch_ctx: BatchContext,
    result: TransferResult,
) -> None:
    """Ejecuta on_transfer_advanced si está definido. Errores logueados."""
    script = _load_event_script(application, "on_transfer_advanced")
    if script is None:
        return

    engine = ScriptEngine()
    try:
        engine.compile_script(
            "on_transfer_advanced",
            script,
            "on_transfer_advanced",
        )
        engine.run_event(
            "on_transfer_advanced",
            "on_transfer_advanced",
            app=app_ctx,
            batch=batch_ctx,
            result=result,
        )
    except ScriptCompilationError as e:
        log.warning(
            "Error compilando on_transfer_advanced (app %d): %s",
            application.id,
            e,
        )
    except Exception as e:
        log.warning(
            "Error ejecutando on_transfer_advanced (app %d): %s",
            application.id,
            e,
        )
    finally:
        engine.shutdown()


# Registrar para que enqueue_or_run lo encuentre en modo inline.
from web.api.tasks.queue import register_inline_runner  # noqa: E402

register_inline_runner("run_transfer_for_batch", run_transfer_for_batch)
