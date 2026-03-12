"""Worker de transferencia en hilo secundario.

Ejecuta TransferService.transfer() sin bloquear la UI.
Soporta modo estándar y modo avanzado (script).
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
        """Ejecuta la transferencia (estándar o avanzada)."""
        try:
            if self._script_engine and self._advanced_contexts:
                result = self._script_engine.run_event(
                    script_id="on_transfer_advanced",
                    entry_point="on_transfer_advanced",
                    pages=self._pages,
                    **self._advanced_contexts,
                )
                from app.services.transfer_service import TransferResult
                if not isinstance(result, TransferResult):
                    result = TransferResult(
                        success=result is not False,
                        files_transferred=len(self._pages),
                    )
                self.transfer_finished.emit(result)
            else:
                def on_page(page_index: int, success: bool) -> None:
                    self.page_transferred.emit(page_index, success)

                result = self._transfer_service.transfer(
                    pages=self._pages,
                    config=self._config,
                    batch_fields=self._batch_fields,
                    batch_id=self._batch_id,
                    on_page_callback=on_page,
                )
                self.transfer_finished.emit(result)
        except Exception as e:
            log.error("Error en transferencia: %s", e)
            self.transfer_error.emit(str(e))
