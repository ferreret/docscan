"""Worker de reconocimiento (pipeline) en hilo secundario.

Recibe imágenes vía cola thread-safe y ejecuta PipelineExecutor
por cada página. Emite señales con los resultados para que el
hilo principal persista en BD.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from app.pipeline.page_context import (  # noqa: F401 — re-export
    AppContext,
    BatchContext,
    BarcodeResult,
    PageContext,
    PageFlags,
)

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Sentinel para señalizar fin de cola
# ------------------------------------------------------------------

_SENTINEL = object()


class RecognitionWorker(QThread):
    """Hilo de reconocimiento de páginas.

    Signals:
        page_processed: (page_index, PageContext) por cada página.
        all_processed: cuando todas las páginas han sido procesadas.
        page_error: (page_index, error_message).
        progress: (completed, total).
    """

    page_processed = Signal(int, object)  # (index, PageContext)
    all_processed = Signal()
    page_error = Signal(int, str)
    progress = Signal(int, int)  # (completed, total)

    def __init__(
        self,
        executor: Any,
        app_context: AppContext,
        batch_context: BatchContext,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._executor = executor
        self._app_ctx = app_context
        self._batch_ctx = batch_context
        self._queue: queue.Queue = queue.Queue()
        self._total_pages: int = 0
        self._completed: int = 0

    def enqueue_page(self, page_index: int, image: np.ndarray) -> None:
        """Encola una página para procesamiento (thread-safe)."""
        self._total_pages += 1
        self._queue.put((page_index, image))

    def signal_no_more_pages(self) -> None:
        """Indica que no llegarán más páginas."""
        self._queue.put(_SENTINEL)

    def run(self) -> None:
        """Procesa páginas de la cola hasta recibir el sentinel."""
        while True:
            if self.isInterruptionRequested():
                log.info("RecognitionWorker interrumpido")
                break

            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is _SENTINEL:
                break

            page_index, image = item
            try:
                page_ctx = PageContext(page_index=page_index, image=image)
                self._executor.execute(
                    page=page_ctx,
                    batch=self._batch_ctx,
                    app=self._app_ctx,
                )
                self._completed += 1
                self.progress.emit(self._completed, self._total_pages)
                self.page_processed.emit(page_index, page_ctx)
            except Exception as e:
                log.error("Error procesando página %d: %s", page_index, e)
                self._completed += 1
                self.progress.emit(self._completed, self._total_pages)
                self.page_error.emit(page_index, str(e))

        self.all_processed.emit()
