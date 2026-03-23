"""Punto de entrada de DocScan Studio.

Modos de ejecución:
    python3.14 main.py                          # Launcher (UI)
    python3.14 main.py "App Name"               # Abre workbench directamente
    python3.14 main.py --direct-mode "App Name" # Headless: escanea y transfiere
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from config.settings import get_settings, APP_DATA_DIR, APP_IMAGES_DIR
from app.db.database import create_db_engine, create_tables, get_session_factory

# Importar todos los modelos para que SQLAlchemy registre las relaciones
from app.models.application import Application  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401


def setup_logging(settings) -> None:
    """Configura el logging según settings."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_args() -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="DocScan Studio",
        # Permitir args desconocidos para Qt
    )
    parser.add_argument(
        "app_name", nargs="?", default=None,
        help="Nombre de la aplicación a abrir directamente",
    )
    parser.add_argument(
        "--direct-mode", action="store_true",
        help="Modo directo: escanea y transfiere sin interfaz (LCH-09)",
    )
    # Parsear solo args conocidos; el resto va a Qt
    args, _qt_args = parser.parse_known_args()
    return args


def _run_direct_mode(app_name: str, session_factory) -> int:
    """Ejecuta modo directo: escanea, procesa pipeline y transfiere.

    Sin interfaz gráfica. Usa el escáner configurado para adquirir
    imágenes, ejecuta el pipeline completo y transfiere.
    """
    log = logging.getLogger(__name__)

    from app.db.repositories.application_repo import ApplicationRepository
    from app.pipeline.executor import PipelineExecutor
    from app.pipeline.serializer import deserialize
    from app.pipeline.steps import ScriptStep
    from app.services.batch_service import BatchService
    from app.services.image_pipeline import ImagePipelineService
    from app.services.import_service import ImportService
    from app.services.script_engine import ScriptEngine
    from app.services.transfer_service import TransferService, parse_transfer_config
    from app.workers.recognition_worker import (
        AppContext, BatchContext, PageContext,
    )

    # Cargar aplicación
    with session_factory() as session:
        repo = ApplicationRepository(session)
        app_record = repo.get_by_name(app_name)
        if app_record is None:
            log.error("Aplicación no encontrada: '%s'", app_name)
            return 1
        if not app_record.active:
            log.error("Aplicación '%s' está desactivada", app_name)
            return 1
        session.expunge(app_record)

    log.info("Modo directo: app='%s'", app_record.name)

    # Construir servicios
    script_engine = ScriptEngine()
    steps = deserialize(app_record.pipeline_json)
    for step in steps:
        if isinstance(step, ScriptStep) and step.script:
            try:
                script_engine.compile_step(step)
            except Exception as exc:
                log.error("Error compilando script '%s': %s", step.label, exc)

    settings = get_settings()
    executor = PipelineExecutor(
        steps=steps,
        image_service=ImagePipelineService(),
        script_engine=script_engine,
        max_repeats=settings.pipeline.max_step_repeats,
    )
    import_service = ImportService()
    images_dir = APP_IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)

    # Escanear usando el backend configurado
    try:
        from app.services.scanner_service import get_scanner
        scanner = get_scanner(app_record.scanner_backend)
        log.info("Escaneando con backend '%s'...", app_record.scanner_backend)
        images = scanner.scan()
    except Exception as exc:
        log.error("Error al escanear: %s", exc)
        return 1

    if not images:
        log.warning("No se obtuvieron imágenes del escáner")
        return 1

    # Crear lote, procesar y transferir
    with session_factory() as session:
        batch_svc = BatchService(session, images_dir)
        batch = batch_svc.create_batch(application_id=app_record.id)
        pages_db = batch_svc.add_pages(
            batch.id, images, app_record.output_format,
        )
        batch_svc.transition_state(batch.id, "read")
        session.commit()

        app_ctx = AppContext(id=app_record.id, name=app_record.name)
        batch_ctx = BatchContext(id=batch.id, state="read")

        t_start = time.monotonic()
        for page_db, image in zip(pages_db, images):
            page_ctx = PageContext(page_index=page_db.page_index, image=image)
            try:
                executor.execute(page=page_ctx, batch=batch_ctx, app=app_ctx)
            except Exception as exc:
                log.error("Error pipeline página %d: %s", page_db.page_index, exc)

            page_db.ocr_text = page_ctx.ocr_text
            page_db.index_fields_json = json.dumps(page_ctx.fields)
            page_db.needs_review = page_ctx.flags.needs_review
            page_db.processing_errors_json = json.dumps(
                page_ctx.flags.processing_errors,
            )

        batch_svc.transition_state(batch.id, "ready_to_export")
        session.commit()

        duration = time.monotonic() - t_start
        log.info(
            "Pipeline completado: %d páginas en %.1fs",
            len(pages_db), duration,
        )

        # Transferir
        config = parse_transfer_config(app_record.transfer_json)
        if config.destination:
            transfer_svc = TransferService()
            pages_data = [
                {
                    "image_path": p.image_path,
                    "page_index": p.page_index,
                    "fields": json.loads(p.index_fields_json),
                    "ocr_text": p.ocr_text,
                }
                for p in pages_db
            ]
            result = transfer_svc.transfer(
                pages_data, config,
                batch_fields=batch_svc.get_fields(batch.id),
                batch_id=batch.id,
            )
            if result.success:
                batch_svc.transition_state(batch.id, "exported")
                log.info("Transferido: %s", result.output_path)
            else:
                batch_svc.transition_state(batch.id, "error_export")
                log.error("Error de transferencia: %s", result.errors)
            session.commit()
        else:
            log.warning("Sin destino de transferencia configurado")

    return 0


def _run_init_global(session_factory) -> None:
    """Busca y ejecuta init_global en las aplicaciones configuradas."""
    _log = logging.getLogger(__name__)
    from app.db.repositories.application_repo import ApplicationRepository
    from app.services.script_engine import ScriptEngine

    with session_factory() as session:
        repo = ApplicationRepository(session)
        apps = repo.get_all()
        for app_record in apps:
            if not app_record.active:
                continue
            try:
                events = json.loads(app_record.events_json or "{}")
            except Exception:
                continue
            source = events.get("init_global", "")
            if source and source.strip():
                engine = ScriptEngine()
                try:
                    engine.compile_script("init_global", source, "init_global")
                    engine.run_event(
                        script_id="init_global",
                        entry_point="init_global",
                    )
                    _log.info(
                        "init_global ejecutado desde app '%s'", app_record.name,
                    )
                except Exception as e:
                    _log.error("Error en init_global: %s", e)
                return  # Solo ejecutar una vez


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    log = logging.getLogger(__name__)

    args = _parse_args()

    log.info("Iniciando %s", settings.app_name)

    # Base de datos
    engine = create_db_engine()
    create_tables(engine)
    session_factory = get_session_factory(engine)

    # ------------------------------------------------------------------
    # Modo directo (LCH-09): sin UI
    # ------------------------------------------------------------------
    if args.direct_mode:
        if not args.app_name:
            log.error("--direct-mode requiere nombre de aplicación")
            return 1
        return _run_direct_mode(args.app_name, session_factory)

    # ------------------------------------------------------------------
    # Modo UI (launcher o workbench directo)
    # ------------------------------------------------------------------
    from PySide6.QtWidgets import QApplication

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(settings.app_name)

    # H1: Liberar engine al salir
    qt_app.aboutToQuit.connect(lambda: engine.dispose())

    # Aplicar tema (restaura preferencias guardadas)
    from app.ui.theme_manager import ThemeManager

    theme_mgr = ThemeManager()
    theme_mgr.apply_theme(theme_mgr.current_theme)

    # Ejecutar init_global si alguna aplicación lo define
    _run_init_global(session_factory)

    # Launcher
    from app.ui.launcher.launcher_window import LauncherWindow

    launcher = LauncherWindow(session_factory=session_factory)

    _workbenches: list = []  # Mantener referencia para evitar GC

    def on_app_opened(app_id: int):
        from app.ui.workbench.workbench_window import WorkbenchWindow

        log.info("Abriendo workbench para app %d", app_id)
        try:
            workbench = WorkbenchWindow(app_id, session_factory)
            workbench.closed.connect(launcher.show)
            workbench.closed.connect(
                lambda w=workbench: _workbenches.remove(w) if w in _workbenches else None
            )
            _workbenches.append(workbench)
            launcher.hide()
            workbench.show()
        except Exception as e:
            log.error("Error abriendo workbench: %s", e)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                launcher, "Error",
                f"No se pudo abrir la aplicación:\n{e}",
            )

    def on_app_configure(app_id: int):
        from app.db.repositories.application_repo import ApplicationRepository
        from app.ui.configurator.app_configurator import AppConfigurator

        with session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_id(app_id)
            if app is None:
                log.error("App %d no encontrada", app_id)
                return
            # Expunge para que sea independiente de la sesión
            session.expunge(app)

        dialog = AppConfigurator(app, session_factory, parent=launcher)
        dialog.exec()
        launcher._load_apps()  # Refrescar la lista

    _batch_managers: list = []  # Mantener referencia para evitar GC

    def on_open_batch(app_id: int, batch_id: int):
        from app.ui.workbench.workbench_window import WorkbenchWindow

        log.info("Abriendo lote %d de app %d", batch_id, app_id)
        try:
            workbench = WorkbenchWindow(
                app_id, session_factory, batch_id=batch_id,
            )
            workbench.closed.connect(launcher.show)
            workbench.closed.connect(
                lambda w=workbench: _workbenches.remove(w) if w in _workbenches else None
            )
            _workbenches.append(workbench)
            launcher.hide()
            workbench.show()
        except Exception as e:
            log.error("Error abriendo lote: %s", e)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                launcher, "Error",
                f"No se pudo abrir el lote:\n{e}",
            )

    def on_batch_manager():
        from app.ui.batch_manager.batch_manager_window import BatchManagerWindow

        log.info("Abriendo gestor de lotes")
        bm = BatchManagerWindow(session_factory)
        bm.closed.connect(lambda: log.info("Gestor de lotes cerrado"))
        bm.closed.connect(
            lambda b=bm: _batch_managers.remove(b) if b in _batch_managers else None
        )
        bm.open_batch_requested.connect(on_open_batch)
        _batch_managers.append(bm)
        bm.show()

    launcher.app_opened.connect(on_app_opened)
    launcher.app_configure.connect(on_app_configure)
    launcher.batch_manager_requested.connect(on_batch_manager)

    # Lanzar workbench directo si se pasa nombre de app (LCH-08)
    if args.app_name:
        from app.db.repositories.application_repo import ApplicationRepository

        with session_factory() as session:
            repo = ApplicationRepository(session)
            app_record = repo.get_by_name(args.app_name)
            if app_record is None:
                log.error("Aplicación no encontrada: '%s'", args.app_name)
                launcher.show()
            else:
                on_app_opened(app_record.id)
    else:
        launcher.show()

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
