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

    def on_app_opened(app_id: int):
        log.info("Abrir workbench para app %d (pendiente de implementar)", app_id)

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

    launcher.app_opened.connect(on_app_opened)
    launcher.app_configure.connect(on_app_configure)
    launcher.show()

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
