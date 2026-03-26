"""Workers de actualización para DocScan Studio.

QThread wrappers sobre UpdateService para integración con la UI sin
bloquear el hilo principal.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.update_service import (
    ReleaseInfo,
    UpdateCheckResult,
    UpdateService,
)

log = logging.getLogger(__name__)


class UpdateCheckWorker(QThread):
    """Comprueba si hay actualizaciones en segundo plano.

    Signals:
        update_available: Emitida con ReleaseInfo si hay versión nueva.
        no_update: Emitida si ya estamos en la última versión.
        check_error: Emitida con mensaje de error si falla la comprobación.
    """

    update_available = Signal(object)  # ReleaseInfo
    no_update = Signal()
    check_error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = UpdateService()

    def run(self) -> None:
        result: UpdateCheckResult = self._service.check_for_update()

        if result.error and not result.available:
            self.check_error.emit(result.error)
        elif result.available and result.latest:
            self.update_available.emit(result.latest)
        else:
            self.no_update.emit()


class UpdateDownloadWorker(QThread):
    """Descarga y verifica una actualización en segundo plano.

    Signals:
        progress: (bytes_descargados, bytes_totales).
        download_finished: Ruta del fichero descargado y verificado.
        download_error: Mensaje de error si falla.
    """

    progress = Signal(int, int)
    download_finished = Signal(str)  # path
    download_error = Signal(str)

    def __init__(
        self,
        release: ReleaseInfo,
        dest_dir: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._dest_dir = dest_dir
        self._service = UpdateService()

    def run(self) -> None:
        try:
            path = self._service.download_update(
                self._release,
                self._dest_dir,
                on_progress=lambda d, t: self.progress.emit(d, t),
            )

            if self._release.sha256:
                if not self._service.verify_checksum(path, self._release.sha256):
                    path.unlink(missing_ok=True)
                    self.download_error.emit(
                        "Error de integridad: el checksum no coincide"
                    )
                    return

            self.download_finished.emit(str(path))

        except Exception as e:
            log.error("Error al descargar actualización: %s", e)
            self.download_error.emit(str(e))
