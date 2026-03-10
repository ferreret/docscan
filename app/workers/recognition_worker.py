"""Worker de reconocimiento (pipeline) en hilo secundario.

Recibe imágenes vía cola thread-safe y ejecuta PipelineExecutor
por cada página. Emite señales con los resultados para que el
hilo principal persista en BD.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Contextos ligeros para el pipeline (duck-type compatible)
# ------------------------------------------------------------------


@dataclass
class PageFlags:
    """Flags mutables de una página durante el pipeline."""

    needs_review: bool = False
    review_reason: str = ""
    script_errors: list[dict[str, Any]] = field(default_factory=list)
    processing_errors: list[str] = field(default_factory=list)


@dataclass
class BarcodeResult:
    """Resultado de barcode detectado por el pipeline."""

    value: str = ""
    symbology: str = ""
    engine: str = ""
    step_id: str = ""
    quality: float = 0.0
    pos_x: int = 0
    pos_y: int = 0
    pos_w: int = 0
    pos_h: int = 0
    role: str = ""


@dataclass
class PageContext:
    """Contexto de página que el PipelineExecutor manipula.

    Compatible duck-type con los accesos que hace el executor:
    ``page.image``, ``page.barcodes``, ``page.ocr_text``,
    ``page.ai_fields``, ``page.flags``.
    """

    page_index: int
    image: np.ndarray | None = None
    barcodes: list[BarcodeResult] = field(default_factory=list)
    ocr_text: str = ""
    ai_fields: dict[str, Any] = field(default_factory=dict)
    flags: PageFlags = field(default_factory=PageFlags)
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchContext:
    """Contexto ligero de lote para scripts."""

    id: int = 0
    fields: dict[str, Any] = field(default_factory=dict)
    state: str = "created"


@dataclass
class AppContext:
    """Contexto ligero de aplicación para scripts."""

    id: int = 0
    name: str = ""
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)


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
