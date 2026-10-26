"""Worker de transferencia en hilo secundario.

Ejecuta el flujo de ``app.services.transfer_flow`` (transferencia estándar y
después ``on_transfer_advanced``) sin bloquear la UI. El worker desatendido
usa el mismo flujo, así que los dos contextos se comportan igual.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.services.transfer_flow import execute_transfer

log = logging.getLogger(__name__)


class TransferWorker(QThread):
    """Hilo de transferencia de lotes.

    Signals:
        transfer_finished: TransferResult al completar. Si el script avanzado
            falla, llega con ``success=False`` y el motivo en ``errors``.
        transfer_error: mensaje de un fallo inesperado del propio flujo.
        page_transferred: (page_index, success) por cada página copiada.
    """

    transfer_finished = Signal(object)  # TransferResult
    transfer_error = Signal(str)
    page_transferred = Signal(int, bool)  # (page_index, success)

    def __init__(
        self,
        transfer_service: Any,
        config: Any,
        pages: list[dict[str, Any]],
        batch_fields: dict[str, str],
        batch_id: int,
        parent: Any = None,
        *,
        script_engine: Any = None,
        advanced_contexts: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._transfer_service = transfer_service
        self._config = config
        self._pages = pages
        self._batch_fields = batch_fields
        self._batch_id = batch_id
        self._script_engine = script_engine
        self._advanced_contexts = advanced_contexts

    def run(self) -> None:
        """Ejecuta la transferencia (estándar y/o avanzada)."""
        try:
            result = execute_transfer(
                transfer_service=self._transfer_service,
                config=self._config,
                pages=self._pages,
                batch_fields=self._batch_fields,
                batch_id=self._batch_id,
                script_engine=self._script_engine,
                contexts=self._advanced_contexts,
                on_page_callback=self.page_transferred.emit,
            )
            self.transfer_finished.emit(result)
        except Exception as e:
            log.exception("Error en transferencia")
            self.transfer_error.emit(str(e))
