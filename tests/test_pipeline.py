"""Tests del pipeline: steps, context y serializer."""

import numpy as np
import pytest

from app.pipeline.context import PipelineAbortError, PipelineContext
from app.pipeline.serializer import (
    PipelineSerializationError,
    deserialize,
    serialize,
)
from app.pipeline.steps import (
    AiStep,
    BarcodeStep,
    ImageOpStep,
    OcrStep,
    ScriptStep,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_steps() -> list:
    return [
        ImageOpStep(id="s1", op="AutoDeskew"),
        BarcodeStep(
            id="s2",
            engine="motor1",
            symbologies=["Code128", "QR"],
            window=(10, 20, 100, 200),
        ),
        ScriptStep(
            id="s3",
            label="Clasificar",
            entry_point="classify",
            script="def classify(app, batch, page, pipeline): pass",
        ),
        OcrStep(id="s4", engine="rapidocr", languages=["es", "en"]),
        AiStep(id="s5", provider="anthropic", template_id=1),
    ]


# ------------------------------------------------------------------
# Steps
# ------------------------------------------------------------------


class TestSteps:
    def test_image_op_defaults(self):
        step = ImageOpStep(id="x", op="Rotate")
        assert step.type == "image_op"
        assert step.enabled is True
        assert step.params == {}
        assert step.window is None

    def test_barcode_defaults(self):
        step = BarcodeStep(id="x")
        assert step.engine == "motor1"
        assert step.symbologies == []
        assert step.orientations == ["horizontal", "vertical"]



# ------------------------------------------------------------------
# Serializer
# ------------------------------------------------------------------


class TestSerializer:
    def test_roundtrip(self, sample_steps):
        """Serializar y deserializar produce pasos equivalentes."""
        json_str = serialize(sample_steps)
        restored = deserialize(json_str)

        assert len(restored) == len(sample_steps)
        for original, loaded in zip(sample_steps, restored):
            assert type(original) is type(loaded)
            assert original.id == loaded.id
            assert original.type == loaded.type

    def test_window_tuple_preserved(self, sample_steps):
        """El campo window (tuple) sobrevive al roundtrip JSON."""
        json_str = serialize(sample_steps)
        restored = deserialize(json_str)
        barcode = restored[1]
        assert isinstance(barcode, BarcodeStep)
        assert barcode.window == (10, 20, 100, 200)
        assert isinstance(barcode.window, tuple)

    def test_symbologies_preserved(self, sample_steps):
        json_str = serialize(sample_steps)
        restored = deserialize(json_str)
        assert restored[1].symbologies == ["Code128", "QR"]

    def test_script_content_preserved(self, sample_steps):
        json_str = serialize(sample_steps)
        restored = deserialize(json_str)
        assert "classify" in restored[2].script

    def test_invalid_json_raises(self):
        with pytest.raises(PipelineSerializationError, match="JSON inválido"):
            deserialize("not json")

    def test_not_a_list_raises(self):
        with pytest.raises(PipelineSerializationError, match="lista"):
            deserialize('{"type": "image_op"}')

    def test_missing_type_raises(self):
        with pytest.raises(PipelineSerializationError, match="falta"):
            deserialize('[{"id": "s1"}]')

    def test_unknown_type_raises(self):
        with pytest.raises(PipelineSerializationError, match="desconocido"):
            deserialize('[{"id": "s1", "type": "magic"}]')

    def test_extra_fields_ignored(self):
        """Campos desconocidos no rompen la deserialización."""
        json_str = '[{"id": "s1", "type": "image_op", "op": "Rotate", "future_field": true}]'
        steps = deserialize(json_str)
        assert len(steps) == 1
        assert steps[0].op == "Rotate"

    def test_empty_pipeline(self):
        assert deserialize("[]") == []
        assert serialize([]) == "[]"


# ------------------------------------------------------------------
# PipelineContext
# ------------------------------------------------------------------


class TestPipelineContext:
    def test_iteration_order(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        ids = []
        while ctx.has_next():
            ids.append(ctx.next_step().id)
        assert ids == ["s1", "s2", "s3", "s4", "s5"]

    def test_skip_step(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        ctx.skip_step("s3")
        assert ctx.is_skipped("s3")
        assert not ctx.is_skipped("s1")

    def test_skip_to(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        ctx.next_step()  # s1
        ctx.skip_to("s4")  # saltar s2, s3
        step = ctx.next_step()
        assert step.id == "s4"

    def test_abort(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        with pytest.raises(PipelineAbortError):
            ctx.abort("motivo de prueba")
        assert ctx.aborted is True
        assert ctx.abort_reason == "motivo de prueba"
        assert ctx.has_next() is False

    def test_repeat_step(self, sample_steps):
        ctx = PipelineContext(sample_steps, max_repeats=2)
        # Avanzar hasta agotar la lista
        while ctx.has_next():
            ctx.next_step()

        ctx.repeat_step("s1")
        assert ctx.has_next()
        repeated = ctx.next_step()
        assert repeated.id == "s1"

    def test_repeat_step_limit(self, sample_steps):
        ctx = PipelineContext(sample_steps, max_repeats=2)
        ctx.repeat_step("s1")
        ctx.repeat_step("s1")
        with pytest.raises(PipelineAbortError, match="límite"):
            ctx.repeat_step("s1")

    def test_metadata(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        assert ctx.get_metadata("clave") is None
        ctx.set_metadata("clave", {"dato": 123})
        assert ctx.get_metadata("clave") == {"dato": 123}

    def test_replace_image(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        assert ctx.current_image is None
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        ctx.replace_image(img)
        assert ctx.current_image is not None
        assert ctx.current_image.shape == (50, 50, 3)

    def test_step_results(self, sample_steps):
        ctx = PipelineContext(sample_steps)
        ctx.set_step_result("s1", {"deskew_angle": 1.5})
        assert ctx.get_step_result("s1") == {"deskew_angle": 1.5}
        assert ctx.get_step_result("s99") is None
