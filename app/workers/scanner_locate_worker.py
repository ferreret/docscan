"""Worker que vuelve a localizar un escáner USB que ha cambiado de dirección.

Al desconectar y reconectar un escáner USB, SANE lo nombra con otra
dirección del bus. Volver a listar los dispositivos tarda unos segundos, así
que se hace en este hilo y no en el de la UI; la decisión de qué
dispositivo usar es de ``BaseScanner.resolve_source``.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from app.services.scanner_service import ScannerGoneError

log = logging.getLogger(__name__)


class ScannerLocateWorker(QThread):
    """Ejecuta ``scanner.resolve_source`` en segundo plano.

    Signals:
        located: (nombre guardado, nombre con el que abrirlo ahora).
        not_found: (nombre guardado, dispositivos encontrados o ``None``
            si no se han podido listar).
    """

    located = Signal(str, str)
    not_found = Signal(str, object)  # list[str] | None

    def __init__(
        self,
        scanner: Any,
        source: str,
        force: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._scanner = scanner
        self._source = source
        self._force = force

    def run(self) -> None:
        """Busca el escáner y emite una de las dos señales."""
        try:
            new = self._scanner.resolve_source(self._source, force=self._force)
        except ScannerGoneError as e:
            self.not_found.emit(self._source, e.sources)
            return
        except Exception as e:
            log.warning("No se pudo volver a localizar %s: %s", self._source, e)
            self.not_found.emit(self._source, None)
            return
        self.located.emit(self._source, new)
