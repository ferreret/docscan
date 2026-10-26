"""Red global de excepciones y traza de arranque.

Una excepción no capturada en un slot de Qt o en un hilo solo se imprimía en
stderr, que en el binario empaquetado (sin consola) se pierde: el fallo no
dejaba rastro. FlexibarNET10 cerró lo mismo con una red global (auditorías
2026-08-11 y 2026-08-14) y registra la versión y el ejecutable en cada
arranque (v1.24), para saber desde el log qué versión corre una estación.
"""

from __future__ import annotations

import logging
import platform
import sys
import threading
from types import TracebackType

from app._version import __version__

log = logging.getLogger("docscan.crash")


def _log_unhandled(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    log.critical("Excepción no capturada", exc_info=(exc_type, exc, tb))


def _log_unhandled_thread(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit:
        return
    log.critical(
        "Excepción no capturada en el hilo %s",
        args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_exception_hooks() -> None:
    """Envía al log, con traza completa, toda excepción no capturada.

    Cubre el hilo principal y los slots de Qt (PySide6 llama a
    ``sys.excepthook``) y los ``threading.Thread``.
    """
    sys.excepthook = _log_unhandled
    threading.excepthook = _log_unhandled_thread


def log_startup(component: str) -> None:
    """Registra versión, ejecutable y plataforma al arrancar.

    Args:
        component: Qué arranca (p. ej. ``"DocScan Studio"``, ``"DocScanWorker"``).
    """
    logging.getLogger("docscan").info(
        "%s %s iniciado. Ejecutable: %s · Python %s · %s",
        component,
        __version__,
        sys.executable,
        platform.python_version(),
        platform.platform(),
    )
