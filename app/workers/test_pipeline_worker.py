"""Worker QThread para probar el pipeline sobre una imagen de muestra."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from app.pipeline.test_executor import InstrumentedPipelineExecutor, StepSnapshot
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    PageContext,
    PageFlags,
)

log = logging.getLogger(__name__)


class TestPipelineWorker(QThread):
    """Ejecuta el pipeline instrumentado en hilo secundario.

    Signals:
        finished: (PageContext, list[StepSnapshot]) al completar.
        error_occurred: mensaje de error si falla.
    """

    finished = Signal(object, list)
    error_occurred = Signal(str)

    def __init__(
        self,
        executor: InstrumentedPipelineExecutor,
        image: np.ndarray,
        app_context: AppContext,
        batch_context: BatchContext,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._executor = executor
        self._image = image
        self._app_ctx = app_context
        self._batch_ctx = batch_context

    def run(self) -> None:
        try:
            page = PageContext(page_index=0, image=self._image)
            page, snapshots = self._executor.execute_instrumented(
                page, self._batch_ctx, self._app_ctx,
            )
            self.finished.emit(page, snapshots)
        except Exception as e:
            log.error("Error en TestPipelineWorker: %s", e)
            self.error_occurred.emit(str(e))
