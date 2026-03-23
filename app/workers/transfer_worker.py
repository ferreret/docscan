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
        """Ejecuta la transferencia (avanzada y/o estándar)."""
        try:
            from app.services.transfer_service import TransferResult

            # 1. Transferencia avanzada (script) si existe
            if self._script_engine and self._advanced_contexts:
                # Convertir dicts a objetos con .image cargada
                from types import SimpleNamespace
                import cv2
                page_objects = []
                for pd in self._pages:
                    ns = SimpleNamespace(**pd)
                    img = cv2.imread(pd["image_path"], cv2.IMREAD_UNCHANGED)
                    if img is None:
                        log.warning("No se pudo cargar imagen: %s", pd["image_path"])
                    ns.image = img
                    page_objects.append(ns)

                result = self._script_engine.run_event(
                    script_id="on_transfer_advanced",
                    entry_point="on_transfer_advanced",
                    pages=page_objects,
                    **self._advanced_contexts,
                )
                if not isinstance(result, TransferResult):
                    result = TransferResult(
                        success=result is not False,
                        files_transferred=len(self._pages),
                    )
                # Si no hay transferencia estándar, emitir y salir
                if not self._config.standard_enabled:
                    self.transfer_finished.emit(result)
                    return

            # 2. Transferencia estándar si está habilitada
            if self._config.standard_enabled:
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
            else:
                # Sin avanzada ni estándar: no hay nada que hacer
                self.transfer_finished.emit(TransferResult(
                    success=True, files_transferred=0,
                ))
        except Exception as e:
            log.error("Error en transferencia: %s", e)
            self.transfer_error.emit(str(e))
