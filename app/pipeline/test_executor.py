"""InstrumentedPipelineExecutor — ejecuta pipeline capturando snapshots.

Para la funcionalidad de "Probar pipeline" (IMG-14): ejecuta el pipeline
sobre una imagen de muestra y captura el estado tras cada paso.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.pipeline.context import PipelineAbortError, PipelineContext
from app.pipeline.executor import PipelineExecutor, StepError
from app.pipeline.steps import PipelineStep

log = logging.getLogger(__name__)


@dataclass
class StepSnapshot:
    """Estado capturado tras ejecutar un paso del pipeline."""

    step: PipelineStep
    image: np.ndarray | None = None
    barcodes: list[Any] = field(default_factory=list)
    ocr_text: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    elapsed_ms: float = 0.0


class InstrumentedPipelineExecutor(PipelineExecutor):
    """Ejecutor instrumentado que captura snapshots tras cada paso.

    Reutiliza toda la logica de PipelineExecutor, solo añade
    la captura de estado intermedio.
    """

    def execute_instrumented(
        self, page: Any, batch: Any, app: Any,
    ) -> tuple[Any, list[StepSnapshot]]:
        """Ejecuta el pipeline capturando un snapshot tras cada paso.

        Returns:
            Tupla (page_context, lista_de_snapshots).
        """
        snapshots: list[StepSnapshot] = []
        ctx = PipelineContext(
            steps=self._steps,
            max_repeats=self._max_repeats,
        )

        while ctx.has_next():
            step = ctx.next_step()

            if not step.enabled or ctx.is_skipped(step.id):
                continue

            snapshot = StepSnapshot(step=step)
            t0 = time.perf_counter()

            try:
                result = self._execute_step(step, page, batch, app, ctx)
                ctx.set_step_result(step.id, result)
            except PipelineAbortError as e:
                snapshot.error = f"Pipeline abortado: {e}"
                if hasattr(page, "flags"):
                    page.flags.needs_review = True
                    if str(e):
                        page.flags.review_reason = str(e)
                snapshot.elapsed_ms = (time.perf_counter() - t0) * 1000
                self._capture_state(snapshot, page, ctx)
                snapshots.append(snapshot)
                break
            except StepError as e:
                snapshot.error = str(e)
                self._record_processing_error(page, step, e)
            finally:
                snapshot.elapsed_ms = (time.perf_counter() - t0) * 1000

            self._capture_state(snapshot, page, ctx)
            snapshots.append(snapshot)

        if ctx.image_replaced and ctx.current_image is not None and hasattr(page, "image"):
            page.image = ctx.current_image
            if hasattr(page, "image_replaced"):
                page.image_replaced = True

        return page, snapshots

    def _capture_state(
        self, snapshot: StepSnapshot, page: Any, ctx: PipelineContext,
    ) -> None:
        """Captura una copia del estado actual en el snapshot."""
        img = ctx.current_image if ctx.current_image is not None else getattr(page, "image", None)
        if img is not None:
            snapshot.image = img.copy()

        if hasattr(page, "barcodes"):
            snapshot.barcodes = list(page.barcodes)
        if hasattr(page, "ocr_text"):
            snapshot.ocr_text = page.ocr_text
        if hasattr(page, "fields"):
            snapshot.fields = dict(page.fields)
