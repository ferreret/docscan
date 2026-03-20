"""Tests del ScriptEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.services.script_engine import ScriptEngine, ScriptCompilationError


# ------------------------------------------------------------------
# Objetos mock para simular el contexto del pipeline
# ------------------------------------------------------------------


@dataclass
class MockFlags:
    needs_review: bool = False
    review_reason: str = ""
    script_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MockBarcode:
    value: str = ""
    symbology: str = ""
    role: str = ""


@dataclass
class MockPage:
    page_index: int = 0
    barcodes: list[MockBarcode] = field(default_factory=list)
    ocr_text: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    flags: MockFlags = field(default_factory=MockFlags)


@dataclass
class MockBatch:
    id: int = 1
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class MockApp:
    name: str = "TestApp"


@dataclass
class MockStep:
    id: str = "step_001"
    label: str = "Test Script"
    entry_point: str = "run"
    script: str = ""


@dataclass
class MockPipeline:
    """Pipeline context mock con control de flujo básico."""

    skipped: set[str] = field(default_factory=set)
    _metadata: dict[str, Any] = field(default_factory=dict)

    def skip_step(self, step_id: str) -> None:
        self.skipped.add(step_id)

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self._metadata.get(key)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def engine():
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


@pytest.fixture
def pipeline():
    return MockPipeline()


# ------------------------------------------------------------------
# Compilación
# ------------------------------------------------------------------


class TestCompilation:
    def test_compile_valid_script(self, engine):
        engine.compile_script("s1", "def run(**kw): return 42", "Test")
        assert engine.is_compiled("s1")

    def test_compile_syntax_error(self, engine):
        with pytest.raises(ScriptCompilationError, match="sintaxis"):
            engine.compile_script("s1", "def broken(:", "Bad")

    def test_compile_step(self, engine):
        step = MockStep(script="def run(**kw): pass")
        engine.compile_step(step)
        assert engine.is_compiled(step.id)

    def test_clear_cache(self, engine):
        engine.compile_script("s1", "x = 1")
        engine.clear_cache()
        assert not engine.is_compiled("s1")

    def test_compile_replaces_previous(self, engine):
        engine.compile_script("s1", "def run(**kw): return 1")
        engine.compile_script("s1", "def run(**kw): return 2")
        assert engine.is_compiled("s1")


# ------------------------------------------------------------------
# Ejecución de ScriptStep
# ------------------------------------------------------------------


class TestRunStep:
    def test_basic_execution(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(
            script="def run(app, batch, page, pipeline): return 'ok'"
        )
        engine.compile_step(step)
        result = engine.run_step(step, page, batch, app_ctx, pipeline)
        assert result == "ok"

    def test_script_modifies_page(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(
            script=(
                "def run(app, batch, page, pipeline):\n"
                "    page.flags.needs_review = True\n"
                "    page.flags.review_reason = 'Falta barcode'\n"
            )
        )
        engine.compile_step(step)
        engine.run_step(step, page, batch, app_ctx, pipeline)
        assert page.flags.needs_review is True
        assert page.flags.review_reason == "Falta barcode"

    def test_script_reads_barcodes(self, engine, page, batch, app_ctx, pipeline):
        page.barcodes = [
            MockBarcode(value="SEP-001", symbology="Code128"),
            MockBarcode(value="12345678", symbology="Code128"),
        ]
        step = MockStep(
            entry_point="classify",
            script=(
                "def classify(app, batch, page, pipeline):\n"
                "    for bc in page.barcodes:\n"
                "        if bc.value.startswith('SEP-'):\n"
                "            bc.role = 'separator'\n"
                "        else:\n"
                "            bc.role = 'content'\n"
            ),
        )
        engine.compile_step(step)
        engine.run_step(step, page, batch, app_ctx, pipeline)
        assert page.barcodes[0].role == "separator"
        assert page.barcodes[1].role == "content"

    def test_script_controls_pipeline(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(
            script=(
                "def run(app, batch, page, pipeline):\n"
                "    pipeline.skip_step('step_005')\n"
                "    pipeline.set_metadata('processed', True)\n"
            ),
        )
        engine.compile_step(step)
        engine.run_step(step, page, batch, app_ctx, pipeline)
        assert "step_005" in pipeline.skipped
        assert pipeline.get_metadata("processed") is True

    def test_script_uses_builtins(self, engine, page, batch, app_ctx, pipeline):
        """Los scripts tienen acceso a re, json, datetime, Path."""
        step = MockStep(
            script=(
                "def run(app, batch, page, pipeline):\n"
                "    import re as _  # Verificar que re está disponible\n"
                "    m = re.match(r'^\\d+$', '12345')\n"
                "    data = json.dumps({'ok': True})\n"
                "    now = datetime.datetime.now()\n"
                "    p = Path('/tmp')\n"
                "    return m is not None\n"
            ),
        )
        engine.compile_step(step)
        result = engine.run_step(step, page, batch, app_ctx, pipeline)
        assert result is True

    def test_runtime_error_recorded(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(
            script="def run(app, batch, page, pipeline): raise ValueError('boom')"
        )
        engine.compile_step(step)
        result = engine.run_step(step, page, batch, app_ctx, pipeline)
        assert result is None
        assert len(page.flags.script_errors) == 1
        assert page.flags.script_errors[0]["error"] == "boom"
        assert page.flags.script_errors[0]["type"] == "ValueError"

    def test_missing_entry_point(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(
            entry_point="nonexistent",
            script="def other_func(**kw): pass",
        )
        engine.compile_step(step)
        result = engine.run_step(step, page, batch, app_ctx, pipeline)
        assert result is None

    def test_uncompiled_script(self, engine, page, batch, app_ctx, pipeline):
        step = MockStep(id="not_compiled")
        result = engine.run_step(step, page, batch, app_ctx, pipeline)
        assert result is None


# ------------------------------------------------------------------
# Ejecución de eventos de ciclo de vida
# ------------------------------------------------------------------


class TestRunEvent:
    def test_basic_event(self, engine, batch, app_ctx):
        engine.compile_script(
            "on_app_start",
            "def on_app_start(app, batch): batch.fields['started'] = 'yes'",
        )
        engine.run_event("on_app_start", "on_app_start", app=app_ctx, batch=batch)
        assert batch.fields["started"] == "yes"

    def test_event_with_return(self, engine, batch, app_ctx):
        engine.compile_script(
            "on_transfer_validate",
            "def validate(app, batch): return len(batch.fields) > 0",
        )
        result = engine.run_event(
            "on_transfer_validate", "validate", app=app_ctx, batch=batch,
        )
        assert result is False  # fields está vacío

    def test_event_error_does_not_crash(self, engine, app_ctx):
        engine.compile_script("bad_event", "def run(app): raise RuntimeError('x')")
        result = engine.run_event("bad_event", "run", app=app_ctx)
        assert result is None


