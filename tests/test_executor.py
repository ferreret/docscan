"""Tests del PipelineExecutor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from app.pipeline.executor import PipelineExecutor, StepError
from app.pipeline.steps import (
    ImageOpStep,
    ScriptStep,
)
from app.services.image_pipeline import ImagePipelineService
from app.services.script_engine import ScriptEngine


# ------------------------------------------------------------------
# Mocks
# ------------------------------------------------------------------


@dataclass
class MockFlags:
    needs_review: bool = False
    review_reason: str = ""
    script_errors: list[dict[str, Any]] = field(default_factory=list)
    processing_errors: list[str] = field(default_factory=list)


@dataclass
class MockPage:
    page_index: int = 0
    image: np.ndarray = field(
        default_factory=lambda: np.ones((100, 100, 3), dtype=np.uint8) * 200,
    )
    barcodes: list = field(default_factory=list)
    ocr_text: str = ""
    ai_fields: dict[str, str] = field(default_factory=dict)
    flags: MockFlags = field(default_factory=MockFlags)


@dataclass
class MockBatch:
    id: int = 1
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class MockApp:
    name: str = "TestApp"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def image_service():
    return ImagePipelineService()


@pytest.fixture
def script_engine():
    return ScriptEngine()


@pytest.fixture
def page():
    return MockPage()


@pytest.fixture
def batch():
    return MockBatch()


@pytest.fixture
def app_ctx():
    return MockApp()


def make_executor(
    steps, image_service, script_engine, **kwargs,
) -> PipelineExecutor:
    # Pre-compilar scripts
    for step in steps:
        if hasattr(step, "script") and step.script:
            script_engine.compile_step(step)
    return PipelineExecutor(
        steps=steps,
        image_service=image_service,
        script_engine=script_engine,
        **kwargs,
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestExecutorBasic:
    def test_empty_pipeline(self, image_service, script_engine, page, batch, app_ctx):
        executor = make_executor([], image_service, script_engine)
        result = executor.execute(page, batch, app_ctx)
        assert result is page

    def test_single_image_op(self, image_service, script_engine, page, batch, app_ctx):
        steps = [ImageOpStep(id="s1", op="FxGrayscale")]
        executor = make_executor(steps, image_service, script_engine)
        result = executor.execute(page, batch, app_ctx)
        assert result is page

    def test_multiple_image_ops(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="ConvertTo1Bpp", params={"threshold": 128}),
        ]
        executor = make_executor(steps, image_service, script_engine)
        result = executor.execute(page, batch, app_ctx)
        assert result is page

    def test_disabled_step_skipped(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale", enabled=False),
            ImageOpStep(id="s2", op="FxNegative"),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        # Solo s2 debe haberse ejecutado


class TestExecutorWithScripts:
    def test_script_modifies_page(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ScriptStep(
                id="s1",
                entry_point="mark",
                script="def mark(app, batch, page, pipeline):\n    page.flags.needs_review = True\n",
            ),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        assert page.flags.needs_review is True

    def test_script_skip_step(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ScriptStep(
                id="s1",
                entry_point="skip_next",
                script="def skip_next(app, batch, page, pipeline):\n    pipeline.skip_step('s2')\n",
            ),
            ImageOpStep(id="s2", op="FxNegative"),
            ImageOpStep(id="s3", op="FxGrayscale"),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        # s2 fue saltado, s3 ejecutado

    def test_script_abort(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ScriptStep(
                id="s1",
                entry_point="do_abort",
                script="def do_abort(app, batch, page, pipeline):\n    pipeline.abort('razón de test')\n",
            ),
            ImageOpStep(id="s2", op="FxGrayscale"),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        assert page.flags.needs_review is True
        assert "razón de test" in page.flags.review_reason

    def test_script_error_recorded(self, image_service, script_engine, page, batch, app_ctx):
        steps = [
            ScriptStep(
                id="s1",
                entry_point="bad",
                script="def bad(app, batch, page, pipeline):\n    raise ValueError('boom')\n",
            ),
            ImageOpStep(id="s2", op="FxGrayscale"),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        # El error se registra pero el pipeline continúa
        assert len(page.flags.script_errors) == 1
        assert page.flags.script_errors[0]["error"] == "boom"


class TestExecutorImageFlow:
    def test_image_transforms_chain(self, image_service, script_engine, page, batch, app_ctx):
        """Las transformaciones se encadenan sobre la imagen del contexto."""
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="ConvertTo1Bpp", params={"threshold": 100}),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)

    def test_invalid_op_records_error(self, image_service, script_engine, page, batch, app_ctx):
        steps = [ImageOpStep(id="s1", op="NoExiste")]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        assert len(page.flags.processing_errors) == 1
        assert "NoExiste" in page.flags.processing_errors[0]
