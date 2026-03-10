"""Worker de transferencia en hilo secundario.

Ejecuta TransferService.transfer() sin bloquear la UI.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class TransferWorker(QThread):
    """Hilo de transferencia de lotes.

    Signals:
        transfer_finished: TransferResult al completar.
        transfer_error: mensaje de error.
    """

    transfer_finished = Signal(object)  # TransferResult
    transfer_error = Signal(str)

    def __init__(
        self,
        transfer_service: Any,
        config: Any,
        pages: list[dict[str, Any]],
        batch_fields: dict[str, str],
        batch_id: int,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._transfer_service = transfer_service
        self._config = config
        self._pages = pages
        self._batch_fields = batch_fields
        self._batch_id = batch_id

    def run(self) -> None:
        """Ejecuta la transferencia."""
        try:
            result = self._transfer_service.transfer(
                pages=self._pages,
                config=self._config,
                batch_fields=self._batch_fields,
                batch_id=self._batch_id,
            )
            self.transfer_finished.emit(result)
        except Exception as e:
            log.error("Error en transferencia: %s", e)
            self.transfer_error.emit(str(e))
