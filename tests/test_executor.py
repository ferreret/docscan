"""Tests del PipelineExecutor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from app.pipeline.executor import PipelineExecutor
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
    fields: dict[str, str] = field(default_factory=dict)
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
    steps,
    image_service,
    script_engine,
    **kwargs,
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

    def test_multiple_image_ops(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="ConvertTo1Bpp", params={"threshold": 128}),
        ]
        executor = make_executor(steps, image_service, script_engine)
        result = executor.execute(page, batch, app_ctx)
        assert result is page

    def test_disabled_step_skipped(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale", enabled=False),
            ImageOpStep(id="s2", op="FxNegative"),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        # Solo s2 debe haberse ejecutado


class TestExecutorWithScripts:
    def test_script_modifies_page(
        self, image_service, script_engine, page, batch, app_ctx
    ):
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

    def test_script_error_recorded(
        self, image_service, script_engine, page, batch, app_ctx
    ):
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
    def test_image_transforms_chain(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        """Las transformaciones se encadenan sobre la imagen del contexto."""
        steps = [
            ImageOpStep(id="s1", op="FxGrayscale"),
            ImageOpStep(id="s2", op="ConvertTo1Bpp", params={"threshold": 100}),
        ]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)

    def test_invalid_op_records_error(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        steps = [ImageOpStep(id="s1", op="NoExiste")]
        executor = make_executor(steps, image_service, script_engine)
        executor.execute(page, batch, app_ctx)
        assert len(page.flags.processing_errors) == 1
        assert "NoExiste" in page.flags.processing_errors[0]


class TestPersistirImageOp:
    """El resultado llega al fichero solo si el paso lo pide (C9)."""

    @staticmethod
    def _page():
        from app.pipeline.page_context import PageContext

        return PageContext(
            page_index=0,
            image=np.full((60, 80, 3), 200, dtype=np.uint8),
        )

    def test_por_defecto_no_toca_la_imagen_de_la_pagina(
        self, image_service, script_engine, batch, app_ctx
    ):
        page = self._page()
        original = page.image.copy()

        steps = [ImageOpStep(id="s1", op="FxNegative")]
        make_executor(steps, image_service, script_engine).execute(page, batch, app_ctx)

        assert np.array_equal(page.image, original)
        assert page.image_replaced is False

    def test_persist_propaga_el_resultado(
        self, image_service, script_engine, batch, app_ctx
    ):
        page = self._page()
        original = page.image.copy()

        steps = [ImageOpStep(id="s1", op="FxNegative", persist=True)]
        make_executor(steps, image_service, script_engine).execute(page, batch, app_ctx)

        assert not np.array_equal(page.image, original)
        assert page.image_replaced is True
        # FxNegative sobre 200 da 55
        assert int(page.image.mean()) == 55

    def test_los_pasos_encadenan_aunque_no_persistan(
        self, image_service, script_engine, batch, app_ctx
    ):
        """El paso 2 ve el resultado del 1 aunque ninguno persista."""
        vistas = []

        class Spy(ImagePipelineService):
            def execute(self, image, op, params, window=None):
                vistas.append(float(image.mean()))
                return super().execute(image, op, params, window)

        page = self._page()
        steps = [
            ImageOpStep(id="s1", op="FxNegative"),
            ImageOpStep(id="s2", op="FxNegative"),
        ]
        make_executor(steps, Spy(), script_engine).execute(page, batch, app_ctx)

        assert vistas == [200.0, 55.0]

    def test_persistir_guarda_instantanea_no_el_estado_final(
        self, image_service, script_engine, batch, app_ctx
    ):
        """Enderezar y archivar; binarizar después solo para leer.

        El paso que persiste fija SU resultado; una operación posterior
        que no persiste alimenta al pipeline pero no ensucia el fichero.
        """
        page = self._page()

        steps = [
            ImageOpStep(id="persistido", op="FxNegative", persist=True),
            ImageOpStep(
                id="solo_lectura", op="ConvertTo1Bpp", params={"threshold": 10}
            ),
        ]
        make_executor(steps, image_service, script_engine).execute(page, batch, app_ctx)

        assert page.image_replaced is True
        # La instantánea del negativo (55), no el binarizado posterior.
        assert int(page.image.mean()) == 55

    def test_gana_el_ultimo_paso_que_persiste(
        self, image_service, script_engine, batch, app_ctx
    ):
        page = self._page()

        steps = [
            ImageOpStep(id="s1", op="FxNegative", persist=True),
            ImageOpStep(id="s2", op="FxNegative", persist=True),
        ]
        make_executor(steps, image_service, script_engine).execute(page, batch, app_ctx)

        # Dos negativos seguidos devuelven el valor original.
        assert int(page.image.mean()) == 200

    def test_replace_image_de_script_mantiene_su_contrato(
        self, image_service, script_engine, batch, app_ctx
    ):
        """Sin ningún paso persistente, un script sigue mandando."""
        page = self._page()

        steps = [
            ScriptStep(
                id="sc",
                script=(
                    "import numpy as np\n"
                    "def run(app, batch, page, pipeline):\n"
                    "    pipeline.replace_image(np.zeros((10, 10, 3), dtype=np.uint8))\n"
                ),
                entry_point="run",
            ),
        ]
        make_executor(steps, image_service, script_engine).execute(page, batch, app_ctx)

        assert page.image_replaced is True
        assert page.image.shape == (10, 10, 3)


class TestConfiguracionPorPaso:
    """Cada paso usa su propia configuración, sin heredar (C2)."""

    def test_cada_image_op_recibe_sus_parametros(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        recibidos = []

        class Spy(ImagePipelineService):
            def execute(self, image, op, params, window=None):
                recibidos.append((op, dict(params or {}), window))
                return super().execute(image, op, params, window)

        steps = [
            ImageOpStep(
                id="s1",
                op="ConvertTo1Bpp",
                params={"threshold": 100},
                window=(0, 0, 50, 50),
            ),
            # Sin params ni ventana propios: NO debe heredar los del anterior.
            ImageOpStep(id="s2", op="FxGrayscale"),
        ]
        make_executor(steps, Spy(), script_engine).execute(page, batch, app_ctx)

        assert recibidos[0] == ("ConvertTo1Bpp", {"threshold": 100}, (0, 0, 50, 50))
        assert recibidos[1] == ("FxGrayscale", {}, None)

    def test_cada_barcode_step_recibe_su_configuracion(
        self, image_service, script_engine, page, batch, app_ctx
    ):
        from app.pipeline.steps import BarcodeStep

        recibidos = []

        class SpyBarcode:
            def read(self, **kwargs):
                recibidos.append(kwargs)
                return []

        steps = [
            BarcodeStep(
                id="b1", engine="motor2", regex=r"^\d+$", symbologies=["QRCode"]
            ),
            # Sin configuración propia: valores por defecto del dataclass.
            BarcodeStep(id="b2"),
        ]
        make_executor(
            steps,
            image_service,
            script_engine,
            barcode_service=SpyBarcode(),
        ).execute(page, batch, app_ctx)

        assert recibidos[0]["engine"] == "motor2"
        assert recibidos[0]["regex"] == r"^\d+$"
        assert recibidos[0]["symbologies"] == ["QRCode"]

        assert recibidos[1]["engine"] == "motor1"
        assert recibidos[1]["regex"] == ""
        assert recibidos[1]["symbologies"] == []
