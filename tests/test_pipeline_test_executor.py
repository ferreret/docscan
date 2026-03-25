"""Tests para InstrumentedPipelineExecutor — prueba de pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.steps import BarcodeStep, ImageOpStep, OcrStep, ScriptStep
from app.pipeline.test_executor import InstrumentedPipelineExecutor, StepSnapshot
from app.services.image_pipeline import ImagePipelineService
from app.services.script_engine import ScriptEngine
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    PageContext,
    PageFlags,
)


def _make_image(w: int = 100, h: int = 80) -> np.ndarray:
    """Crea una imagen BGR de prueba."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_executor(steps, barcode_service=None, ocr_service=None):
    """Crea un InstrumentedPipelineExecutor con servicios reales."""
    image_service = ImagePipelineService()
    script_engine = ScriptEngine()
    for s in steps:
        if isinstance(s, ScriptStep):
            script_engine.compile_step(s)
    return InstrumentedPipelineExecutor(
        steps=steps,
        image_service=image_service,
        script_engine=script_engine,
        barcode_service=barcode_service,
        ocr_service=ocr_service,
    )


class TestSnapshotsCapture:
    def test_empty_pipeline_returns_no_snapshots(self):
        executor = _make_executor([])
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert snaps == []

    def test_single_image_op_produces_one_snapshot(self):
        steps = [ImageOpStep(id="s1", op="FxGrayscale")]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert len(snaps) == 1
        assert snaps[0].step.id == "s1"
        assert snaps[0].error is None
        assert snaps[0].elapsed_ms > 0
        assert snaps[0].image is not None

    def test_multiple_steps_produce_multiple_snapshots(self):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="FxNegative"),
            ImageOpStep(id="s3", op="Rotate", params={"angle": 180}),
        ]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert len(snaps) == 3
        for snap in snaps:
            assert snap.image is not None
            assert snap.error is None

    def test_disabled_step_is_skipped(self):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="FxNegative", enabled=False),
        ]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert len(snaps) == 1
        assert snaps[0].step.id == "s1"


class TestSnapshotImageIsCopy:
    def test_image_is_independent_copy(self):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="FxGrayscale"),
        ]
        executor = _make_executor(steps)
        # Imagen con valores variados para que la copia sea verificable
        img = np.full((50, 50, 3), 128, dtype=np.uint8)
        page = PageContext(page_index=0, image=img)
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        original_val = snaps[1].image[0, 0].copy()
        # Modificar snapshot 0 no debe afectar snapshot 1
        snaps[0].image[:] = 255
        assert np.array_equal(snaps[1].image[0, 0], original_val)


class TestErrorCapture:
    def test_invalid_op_produces_error_snapshot(self):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="OperacionInventada"),
            ImageOpStep(id="s3", op="FxNegative"),
        ]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert len(snaps) == 3
        assert snaps[0].error is None
        assert snaps[1].error is not None
        assert snaps[2].error is None

    def test_script_abort_stops_pipeline(self):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ScriptStep(
                id="s2",
                label="Abort",
                entry_point="process",
                script='def process(app, batch, page, pipeline):\n    pipeline.abort("test abort")\n',
            ),
            ImageOpStep(id="s3", op="FxNegative"),
        ]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        # Solo s1 y s2 (s3 no se ejecuta porque abort detiene)
        assert len(snaps) == 2
        assert snaps[1].error is not None
        assert "abort" in snaps[1].error.lower()
        assert page.flags.needs_review is True


class TestScriptFieldsCapture:
    def test_script_fields_captured(self):
        steps = [
            ScriptStep(
                id="s1",
                label="SetField",
                entry_point="process",
                script=(
                    'def process(app, batch, page, pipeline):\n'
                    '    page.fields["doc_type"] = "factura"\n'
                ),
            ),
        ]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert len(snaps) == 1
        assert snaps[0].fields.get("doc_type") == "factura"


class TestElapsedTime:
    def test_elapsed_is_positive(self):
        steps = [ImageOpStep(id="s1", op="FxGrayscale")]
        executor = _make_executor(steps)
        page = PageContext(page_index=0, image=_make_image())
        page, snaps = executor.execute_instrumented(
            page, BatchContext(), AppContext(),
        )
        assert snaps[0].elapsed_ms > 0
