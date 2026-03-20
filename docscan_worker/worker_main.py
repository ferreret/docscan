"""DocScanWorker — proceso CLI desatendido (BAT-08, BAT-11).

Modos de operación:
1. **Folder-watch**: vigila carpeta de entrada, crea y procesa lotes
   automáticamente al detectar ficheros nuevos.
2. **Consume pendientes**: procesa lotes en estado "read" o
   "ready_to_export" que ya existan en BD.

Uso:
    python3.14 -m docscan_worker --app-name "MiApp" --watch /ruta/entrada
    python3.14 -m docscan_worker --app-name "MiApp" --process-pending
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

from config.settings import get_settings, APP_DATA_DIR, APP_IMAGES_DIR

# Importar modelos para que SQLAlchemy registre las relaciones
from app.models.application import Application  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401

from app.db.database import create_db_engine, create_tables, get_session_factory
from app.db.repositories.application_repo import ApplicationRepository
from app.pipeline.executor import PipelineExecutor
from app.pipeline.serializer import deserialize
from app.pipeline.steps import ScriptStep
from app.services.batch_service import BatchService
from app.services.image_pipeline import ImagePipelineService
from app.services.import_service import ImportService
from app.services.notification_service import NotificationService
from app.services.script_engine import ScriptEngine
from app.services.transfer_service import (
    TransferService,
    parse_transfer_config,
)
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    PageContext,
)

log = logging.getLogger(__name__)

# Evento global para shutdown coordinado
_shutdown = threading.Event()


def _setup_logging(level: str = "INFO") -> None:
    """Configura logging para el worker CLI."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="docscan_worker",
        description="DocScan Worker — proceso desatendido de lotes",
    )
    parser.add_argument(
        "--app-name", required=True,
        help="Nombre de la aplicación a ejecutar",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--watch", type=Path, metavar="FOLDER",
        help="Vigilar carpeta de entrada (folder-watch mode)",
    )
    mode.add_argument(
        "--process-pending", action="store_true",
        help="Procesar lotes pendientes en BD y salir",
    )

    parser.add_argument(
        "--debounce", type=int, default=3,
        help="Segundos de inactividad antes de crear lote (default: 3)",
    )
    parser.add_argument(
        "--sentinel", default="",
        help="Nombre de fichero centinela (ej: GO.txt). Activa modo centinela",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


# ------------------------------------------------------------------
# Carga de la aplicación y construcción de servicios
# ------------------------------------------------------------------

def _load_application(session_factory, app_name: str) -> Application:
    """Carga y valida la aplicación desde BD."""
    with session_factory() as session:
        repo = ApplicationRepository(session)
        app_record = repo.get_by_name(app_name)
        if app_record is None:
            log.error("Aplicación no encontrada: '%s'", app_name)
            sys.exit(1)
        if not app_record.active:
            log.error("Aplicación '%s' está desactivada", app_name)
            sys.exit(1)
        session.expunge(app_record)
    return app_record


def _build_executor(
    app_record: Application,
    script_engine: ScriptEngine,
) -> PipelineExecutor:
    """Construye el PipelineExecutor a partir de la config de la app."""
    steps = deserialize(app_record.pipeline_json)

    # Pre-compilar scripts del pipeline
    for step in steps:
        if isinstance(step, ScriptStep) and step.script:
            try:
                script_engine.compile_step(step)
            except Exception as exc:
                log.error(
                    "Error compilando script '%s': %s",
                    step.label or step.id, exc,
                )

    settings = get_settings()
    return PipelineExecutor(
        steps=steps,
        image_service=ImagePipelineService(),
        script_engine=script_engine,
        max_repeats=settings.pipeline.max_step_repeats,
    )


def _compile_lifecycle_events(
    app_record: Application,
    script_engine: ScriptEngine,
) -> dict[str, str]:
    """Compila los scripts de eventos de ciclo de vida.

    Returns:
        Diccionario {event_name: entry_point_name} de eventos compilados.
    """
    events: dict[str, str] = {}
    try:
        events_data = json.loads(app_record.events_json)
    except (json.JSONDecodeError, TypeError):
        return events

    for event_name, event_config in events_data.items():
        if not isinstance(event_config, dict):
            continue
        source = event_config.get("script", "")
        entry_point = event_config.get("entry_point", event_name)
        if not source:
            continue
        try:
            script_engine.compile_script(event_name, source, label=event_name)
            events[event_name] = entry_point
        except Exception as exc:
            log.error("Error compilando evento '%s': %s", event_name, exc)

    return events


# ------------------------------------------------------------------
# Procesamiento de un lote de ficheros
# ------------------------------------------------------------------

def _process_files(
    file_paths: list[Path],
    app_record: Application,
    executor: PipelineExecutor,
    import_service: ImportService,
    script_engine: ScriptEngine,
    lifecycle_events: dict[str, str],
    session_factory,
    images_dir: Path,
) -> None:
    """Importa ficheros, crea lote en BD, ejecuta pipeline y transfiere.

    Este es el flujo completo equivalente al workbench pero sin UI:
    1. Crear lote en BD (estado: created)
    2. Importar ficheros como imágenes
    3. Guardar páginas en BD y disco (estado: read)
    4. Ejecutar pipeline por cada página
    5. Actualizar páginas en BD con resultados
    6. Si auto_transfer: transferir y notificar
    """
    with session_factory() as session:
        batch_svc = BatchService(session, images_dir)
        transfer_svc = TransferService()
        notification_svc = NotificationService()

        # 1. Crear lote
        batch = batch_svc.create_batch(
            application_id=app_record.id,
            folder_path=str(file_paths[0].parent),
        )
        batch_id = batch.id
        log.info(
            "Lote %d creado (%d fichero(s)) para app '%s'",
            batch_id, len(file_paths), app_record.name,
        )

        # Contextos para el pipeline
        app_ctx = AppContext(
            id=app_record.id,
            name=app_record.name,
            description=app_record.description,
        )
        batch_ctx = BatchContext(id=batch_id, state=batch.state)

        # Evento on_app_start
        if "on_app_start" in lifecycle_events:
            script_engine.run_event(
                "on_app_start",
                lifecycle_events["on_app_start"],
                app=app_ctx, batch=batch_ctx,
            )

        # 2-3. Importar ficheros y crear páginas
        all_images = []
        for file_path in file_paths:
            if _shutdown.is_set():
                log.info("Shutdown solicitado, abortando importación")
                batch_svc.transition_state(batch_id, "error_read")
                session.commit()
                return
            try:
                images = import_service.import_file(file_path)
                all_images.extend(images)
            except Exception as exc:
                log.error("Error importando %s: %s", file_path, exc)

        if not all_images:
            log.warning("No se importaron imágenes del lote %d", batch_id)
            batch_svc.transition_state(batch_id, "error_read")
            session.commit()
            return

        pages_db = batch_svc.add_pages(
            batch_id, all_images, app_record.output_format,
        )
        batch_svc.transition_state(batch_id, "read")
        session.commit()

        # 4. Ejecutar pipeline por cada página
        t_start = time.monotonic()
        processed_count = 0
        error_count = 0
        page_contexts: list[tuple[Page, PageContext]] = []

        for page_db, image in zip(pages_db, all_images):
            if _shutdown.is_set():
                log.info("Shutdown solicitado, abortando pipeline")
                break

            page_ctx = PageContext(page_index=page_db.page_index, image=image)
            try:
                executor.execute(page=page_ctx, batch=batch_ctx, app=app_ctx)
                processed_count += 1
            except Exception as exc:
                log.error(
                    "Error en pipeline, página %d: %s",
                    page_db.page_index, exc,
                )
                error_count += 1

            page_contexts.append((page_db, page_ctx))

        # 5. Actualizar páginas en BD con resultados del pipeline
        for page_db, page_ctx in page_contexts:
            page_db.ocr_text = page_ctx.ocr_text
            page_db.custom_fields_json = json.dumps(page_ctx.custom_fields)
            page_db.index_fields_json = json.dumps(page_ctx.fields)
            page_db.needs_review = page_ctx.flags.needs_review
            page_db.review_reason = page_ctx.flags.review_reason
            page_db.processing_errors_json = json.dumps(
                page_ctx.flags.processing_errors,
            )
            page_db.script_errors_json = json.dumps(
                page_ctx.flags.script_errors,
            )

        # Estadísticas
        duration = time.monotonic() - t_start
        stats = {
            "total_pages": len(all_images),
            "processed": processed_count,
            "errors": error_count,
            "needs_review": sum(
                1 for _, pc in page_contexts if pc.flags.needs_review
            ),
            "duration_seconds": round(duration, 2),
            "avg_seconds_per_page": round(
                duration / max(len(all_images), 1), 2,
            ),
        }
        batch = batch_svc.get_batch(batch_id)
        batch.stats_json = json.dumps(stats)

        # Evento on_scan_complete
        if "on_scan_complete" in lifecycle_events:
            script_engine.run_event(
                "on_scan_complete",
                lifecycle_events["on_scan_complete"],
                app=app_ctx, batch=batch_ctx,
            )

        # Transición de estado
        if error_count > 0 and processed_count == 0:
            batch_svc.transition_state(batch_id, "error_read")
        else:
            batch_svc.transition_state(batch_id, "ready_to_export")

        session.commit()

        log.info(
            "Lote %d procesado: %d páginas en %.1fs (%.1f p/s)",
            batch_id, processed_count, duration,
            processed_count / max(duration, 0.001),
        )

        # 6. Auto-transfer si configurado
        if app_record.auto_transfer:
            _transfer_batch(
                batch_id, app_record, batch_svc, transfer_svc,
                notification_svc, script_engine, lifecycle_events,
                session, app_ctx, batch_ctx,
            )


def _transfer_batch(
    batch_id: int,
    app_record: Application,
    batch_svc: BatchService,
    transfer_svc: TransferService,
    notification_svc: NotificationService,
    script_engine: ScriptEngine,
    lifecycle_events: dict[str, str],
    session,
    app_ctx: AppContext,
    batch_ctx: BatchContext,
) -> None:
    """Ejecuta la transferencia de un lote procesado."""
    config = parse_transfer_config(app_record.transfer_json)
    if not config.destination:
        log.warning(
            "Lote %d: no hay destino de transferencia configurado",
            batch_id,
        )
        return

    # Evento on_transfer_validate
    if "on_transfer_validate" in lifecycle_events:
        result = script_engine.run_event(
            "on_transfer_validate",
            lifecycle_events["on_transfer_validate"],
            app=app_ctx, batch=batch_ctx,
        )
        if result is False:
            log.info("Lote %d: transferencia rechazada por validación", batch_id)
            return

    # Preparar datos de páginas para TransferService
    pages_db = batch_svc.get_pages(batch_id)
    pages_data: list[dict[str, Any]] = []
    for p in pages_db:
        if p.is_excluded:
            continue
        pages_data.append({
            "image_path": p.image_path,
            "page_index": p.page_index,
            "index_fields": json.loads(p.index_fields_json),
            "ocr_text": p.ocr_text,
            "custom_fields": json.loads(p.custom_fields_json),
        })

    batch_fields = batch_svc.get_fields(batch_id)
    transfer_result = transfer_svc.transfer(
        pages_data, config, batch_fields, batch_id,
    )

    if transfer_result.success:
        batch_svc.transition_state(batch_id, "exported")
        log.info(
            "Lote %d transferido: %d ficheros → %s",
            batch_id, transfer_result.files_transferred,
            transfer_result.output_path,
        )

        # Evento on_transfer_advanced
        if "on_transfer_advanced" in lifecycle_events:
            script_engine.run_event(
                "on_transfer_advanced",
                lifecycle_events["on_transfer_advanced"],
                app=app_ctx, batch=batch_ctx,
                result=transfer_result,
            )

        # Notificaciones (BAT-11 / MLT-03)
        stats = batch_svc.get_stats(batch_id)
        notification_svc.notify_transfer_complete(
            webhook=None,  # TODO: cargar de app config
            email=None,
            batch_id=batch_id,
            app_name=app_record.name,
            stats=stats,
        )
    else:
        batch_svc.transition_state(batch_id, "error_export")
        log.error(
            "Lote %d: error de transferencia: %s",
            batch_id, transfer_result.errors,
        )
        notification_svc.notify_error(
            webhook=None,
            email=None,
            batch_id=batch_id,
            app_name=app_record.name,
            error="; ".join(transfer_result.errors),
        )

    session.commit()


# ------------------------------------------------------------------
# Procesamiento de lotes pendientes en BD
# ------------------------------------------------------------------

def _process_pending_batches(
    app_record: Application,
    executor: PipelineExecutor,
    import_service: ImportService,
    script_engine: ScriptEngine,
    lifecycle_events: dict[str, str],
    session_factory,
    images_dir: Path,
) -> int:
    """Procesa lotes en estado 'read' o 'ready_to_export'.

    Returns:
        Número de lotes procesados.
    """
    processed = 0
    with session_factory() as session:
        batch_svc = BatchService(session, images_dir)
        transfer_svc = TransferService()
        notification_svc = NotificationService()

        app_ctx = AppContext(
            id=app_record.id,
            name=app_record.name,
            description=app_record.description,
        )

        # Lotes en "read": necesitan pipeline
        for batch in batch_svc.get_batches_by_state("read"):
            if batch.application_id != app_record.id:
                continue
            if _shutdown.is_set():
                break

            log.info("Re-procesando lote %d (estado: read)", batch.id)
            batch_ctx = BatchContext(id=batch.id, state=batch.state)
            pages_db = batch_svc.get_pages(batch.id)

            for page_db in pages_db:
                if _shutdown.is_set():
                    break
                image = batch_svc.get_page_image(page_db)
                if image is None:
                    continue
                page_ctx = PageContext(
                    page_index=page_db.page_index, image=image,
                )
                try:
                    executor.execute(
                        page=page_ctx, batch=batch_ctx, app=app_ctx,
                    )
                except Exception as exc:
                    log.error(
                        "Error pipeline lote %d página %d: %s",
                        batch.id, page_db.page_index, exc,
                    )
                    continue

                page_db.ocr_text = page_ctx.ocr_text
                page_db.custom_fields_json = json.dumps(page_ctx.custom_fields)
                page_db.index_fields_json = json.dumps(page_ctx.fields)
                page_db.needs_review = page_ctx.flags.needs_review
                page_db.review_reason = page_ctx.flags.review_reason
                page_db.processing_errors_json = json.dumps(
                    page_ctx.flags.processing_errors,
                )
                page_db.script_errors_json = json.dumps(
                    page_ctx.flags.script_errors,
                )

            batch_svc.transition_state(batch.id, "ready_to_export")
            session.commit()
            processed += 1

        # Lotes en "ready_to_export": necesitan transferencia
        for batch in batch_svc.get_batches_by_state("ready_to_export"):
            if batch.application_id != app_record.id:
                continue
            if _shutdown.is_set():
                break

            log.info("Transfiriendo lote %d", batch.id)
            batch_ctx = BatchContext(id=batch.id, state=batch.state)
            _transfer_batch(
                batch.id, app_record, batch_svc, transfer_svc,
                notification_svc, script_engine, lifecycle_events,
                session, app_ctx, batch_ctx,
            )
            processed += 1

    return processed


# ------------------------------------------------------------------
# Tareas periódicas para folder-watch
# ------------------------------------------------------------------

def _cleanup_temp_files(watch_folder: Path) -> None:
    """Limpia ficheros temporales antiguos (> 1 hora)."""
    for pattern in ("*.tmp", "*.part"):
        for tmp in watch_folder.glob(pattern):
            try:
                age = time.time() - tmp.stat().st_mtime
                if age > 3600:
                    tmp.unlink()
                    log.info("Temporal eliminado: %s", tmp)
            except OSError:
                pass


def _retry_error_batches(
    app_record: Application,
    executor: PipelineExecutor,
    script_engine: ScriptEngine,
    lifecycle_events: dict[str, str],
    session_factory,
    images_dir: Path,
) -> None:
    """Reintenta lotes en estado de error."""
    with session_factory() as session:
        batch_svc = BatchService(session, images_dir)
        transfer_svc = TransferService()
        notification_svc = NotificationService()

        app_ctx = AppContext(
            id=app_record.id, name=app_record.name,
            description=app_record.description,
        )

        for state in ("error_read", "error_export"):
            for batch in batch_svc.get_batches_by_state(state):
                if batch.application_id != app_record.id:
                    continue

                log.info("Reintentando lote %d (estado: %s)", batch.id, state)
                batch_ctx = BatchContext(id=batch.id, state=batch.state)

                if state == "error_export":
                    _transfer_batch(
                        batch.id, app_record, batch_svc, transfer_svc,
                        notification_svc, script_engine, lifecycle_events,
                        session, app_ctx, batch_ctx,
                    )
                # error_read: se reintentará en el próximo ciclo
                # de process_pending si se corrige el problema


# ------------------------------------------------------------------
# Punto de entrada principal
# ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del worker desatendido."""
    args = _parse_args(argv)
    _setup_logging(args.log_level)

    log.info("DocScan Worker iniciando...")

    # Señales de shutdown
    def _handle_signal(signum, _frame):
        log.info("Señal %d recibida, cerrando...", signum)
        _shutdown.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Base de datos
    engine = create_db_engine()
    create_tables(engine)
    session_factory = get_session_factory(engine)

    # Cargar aplicación
    app_record = _load_application(session_factory, args.app_name)
    log.info("Aplicación cargada: '%s' (id=%d)", app_record.name, app_record.id)

    # Servicios
    script_engine = ScriptEngine()
    lifecycle_events = _compile_lifecycle_events(app_record, script_engine)
    executor = _build_executor(app_record, script_engine)
    import_service = ImportService()
    images_dir = APP_IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Modo: procesar pendientes y salir
    # ------------------------------------------------------------------
    if args.process_pending:
        count = _process_pending_batches(
            app_record, executor, import_service,
            script_engine, lifecycle_events,
            session_factory, images_dir,
        )
        log.info("Procesados %d lote(s) pendiente(s)", count)
        return 0

    # ------------------------------------------------------------------
    # Modo: folder-watch
    # ------------------------------------------------------------------
    watch_folder = args.watch
    if not watch_folder.is_dir():
        log.error("Carpeta de entrada no existe: %s", watch_folder)
        return 1

    from docscan_worker.folder_watcher import FolderWatcher

    def on_batch(file_paths: list[Path]) -> None:
        """Callback del FolderWatcher cuando hay ficheros listos."""
        _process_files(
            file_paths, app_record, executor, import_service,
            script_engine, lifecycle_events, session_factory, images_dir,
        )

    watcher = FolderWatcher(
        watch_folder=watch_folder,
        batch_callback=on_batch,
        debounce_seconds=args.debounce,
        sentinel_filename=args.sentinel,
        cleanup_callback=lambda: _cleanup_temp_files(watch_folder),
        error_retry_callback=lambda: _retry_error_batches(
            app_record, executor, script_engine, lifecycle_events,
            session_factory, images_dir,
        ),
    )

    watcher.start()
    log.info(
        "Worker listo. Vigilando: %s (app='%s')",
        watch_folder, app_record.name,
    )

    try:
        _shutdown.wait()
    finally:
        watcher.stop()

    log.info("Worker terminado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
