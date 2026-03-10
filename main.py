"""Punto de entrada de DocScan Studio."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from config.settings import get_settings
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


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    log = logging.getLogger(__name__)

    log.info("Iniciando %s", settings.app_name)

    # Base de datos
    engine = create_db_engine()
    create_tables(engine)
    session_factory = get_session_factory(engine)

    # Aplicación Qt
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(settings.app_name)

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

    def on_batch_manager():
        from app.ui.batch_manager.batch_manager_window import BatchManagerWindow

        log.info("Abriendo gestor de lotes")
        bm = BatchManagerWindow(session_factory)
        bm.closed.connect(lambda: log.info("Gestor de lotes cerrado"))
        _batch_managers.append(bm)
        bm.show()

    launcher.app_opened.connect(on_app_opened)
    launcher.app_configure.connect(on_app_configure)
    launcher.batch_manager_requested.connect(on_batch_manager)
    launcher.show()

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
