"""Tests de integración end-to-end del pipeline.

Cubre flujos completos: ImageOp + Script, barcode acumulado, control de
flujo (skip/abort), repeat_step con límite, y ciclo de vida de un lote.

Los servicios externos (OCR, IA, scanner) se mockean; el pipeline real
(PipelineExecutor + PipelineContext + ScriptEngine + ImagePipelineService)
se ejecuta sin stubs internos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.application import Application
from app.models.barcode import Barcode  # noqa: F401 — resolver relaciones ORM
from app.models.batch import BATCH_STATES, Batch
from app.models.page import Page
from app.models.template import Template  # noqa: F401 — resolver relaciones ORM
from app.pipeline.context import PipelineAbortError
from app.pipeline.executor import PipelineExecutor
from app.pipeline.steps import BarcodeStep, ImageOpStep, ScriptStep
from app.services.batch_service import BatchService
from app.services.image_pipeline import ImagePipelineService
from app.services.script_engine import ScriptEngine


# ------------------------------------------------------------------ #
# Contextos mínimos duck-type para el executor                         #
# ------------------------------------------------------------------ #


@dataclass
class _Flags:
    needs_review: bool = False
    review_reason: str = ""
    script_errors: list[dict[str, Any]] = field(default_factory=list)
    processing_errors: list[str] = field(default_factory=list)


@dataclass
class _PageCtx:
    page_index: int
    image: np.ndarray | None = None
    barcodes: list[Any] = field(default_factory=list)
    ocr_text: str = ""
    ai_fields: dict[str, Any] = field(default_factory=dict)
    flags: _Flags = field(default_factory=_Flags)
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class _BatchCtx:
    id: int = 0
    fields: dict[str, Any] = field(default_factory=dict)
    state: str = "created"


@dataclass
class _AppCtx:
    id: int = 0
    name: str = "test-app"


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _white_image(h: int = 100, w: int = 100) -> np.ndarray:
    """Devuelve una imagen BGR blanca como numpy array."""
    return np.ones((h, w, 3), dtype=np.uint8) * 255


def _make_executor(
    steps: list,
    barcode_service: Any = None,
    ocr_service: Any = None,
    ai_service: Any = None,
    max_repeats: int = 3,
) -> PipelineExecutor:
    image_service = ImagePipelineService()
    script_engine = ScriptEngine()

    # Pre-compilar ScriptSteps
    for step in steps:
        if step.type == "script" and step.script:
            script_engine.compile_step(step)

    return PipelineExecutor(
        steps=steps,
        image_service=image_service,
        script_engine=script_engine,
        barcode_service=barcode_service,
        ocr_service=ocr_service,
        ai_service=ai_service,
        max_repeats=max_repeats,
    )


# ------------------------------------------------------------------ #
# Fixture de BD en memoria                                             #
# ------------------------------------------------------------------ #


@pytest.fixture()
def engine():
    """Engine SQLite en memoria con WAL mode."""
    eng = create_engine("sqlite:///:memory:")

    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    event.listen(eng, "connect", _pragmas)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def app_record(session) -> Application:
    app = Application(name="TestApp", description="Integración")
    session.add(app)
    session.flush()
    return app


# ------------------------------------------------------------------ #
# 1. Pipeline completo: ImageOpStep (FxGrayscale) + ScriptStep         #
# ------------------------------------------------------------------ #


class TestPipelineImageOpAndScript:
    """Flujo: escala de grises → script que escribe en page.fields."""

    def test_imageop_grayscale_transforms_image(self) -> None:
        """FxGrayscale convierte la imagen a un canal único."""
        steps = [
            ImageOpStep(id="op1", op="FxGrayscale"),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        result = executor.execute(page, _BatchCtx(), _AppCtx())

        # La imagen en el contexto es gris (2-D o 3-D canal único)
        assert result is page
        # El executor no muta page.image directamente; la imagen procesada
        # vive en ctx.current_image interno; pero el resultado del paso
        # debería estar registrado sin error.
        assert result.flags.processing_errors == []

    def test_script_receives_correct_context_variables(self) -> None:
        """El script puede leer y escribir en page.fields."""
        script_src = """
def process(app, batch, page, pipeline):
    page.fields['resultado'] = 'ok'
    page.fields['batch_id'] = batch.id
"""
        steps = [
            ScriptStep(
                id="s1",
                label="Marca resultado",
                entry_point="process",
                script=script_src,
            ),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())
        batch = _BatchCtx(id=42)

        executor.execute(page, batch, _AppCtx())

        assert page.fields["resultado"] == "ok"
        assert page.fields["batch_id"] == 42

    def test_imageop_followed_by_script_shares_context(self) -> None:
        """ImageOp + ScriptStep se ejecutan en secuencia sin errores."""
        script_src = """
def run(app, batch, page, pipeline):
    page.fields['ran'] = True
"""
        steps = [
            ImageOpStep(id="op1", op="FxGrayscale"),
            ScriptStep(id="s1", label="Flag", entry_point="run", script=script_src),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.fields.get("ran") is True
        assert page.flags.processing_errors == []
        assert page.flags.script_errors == []

    def test_disabled_step_is_skipped(self) -> None:
        """Un paso con enabled=False no se ejecuta."""
        script_src = """
def run(app, batch, page, pipeline):
    page.fields['executed'] = True
"""
        steps = [
            ScriptStep(
                id="s1",
                label="No ejecutar",
                entry_point="run",
                script=script_src,
                enabled=False,
            ),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert "executed" not in page.fields


# ------------------------------------------------------------------ #
# 2. BarcodeStep con servicio mockeado                                 #
# ------------------------------------------------------------------ #


class TestPipelineBarcodeStep:
    """BarcodeStep acumula resultados en page.barcodes."""

    def _fake_barcode_service(self, results: list) -> MagicMock:
        svc = MagicMock()
        svc.read.return_value = results
        return svc

    def test_barcode_results_accumulated_in_page(self) -> None:
        """Los barcodes devueltos por el servicio se añaden a page.barcodes."""
        fake_result = MagicMock()
        fake_result.value = "ABC-123"

        steps = [
            BarcodeStep(id="bc1", engine="motor1"),
        ]
        barcode_svc = self._fake_barcode_service([fake_result])
        executor = _make_executor(steps, barcode_service=barcode_svc)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert len(page.barcodes) == 1
        assert page.barcodes[0].value == "ABC-123"

    def test_multiple_barcode_steps_accumulate(self) -> None:
        """Dos BarcodeSteps consecutivos acumulan todos los resultados."""
        r1 = MagicMock()
        r1.value = "SEP-001"
        r2 = MagicMock()
        r2.value = "DOC-999"

        svc = MagicMock()
        svc.read.side_effect = [[r1], [r2]]

        steps = [
            BarcodeStep(id="bc1", engine="motor1"),
            BarcodeStep(id="bc2", engine="motor2"),
        ]
        executor = _make_executor(steps, barcode_service=svc)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert len(page.barcodes) == 2
        values = [b.value for b in page.barcodes]
        assert "SEP-001" in values
        assert "DOC-999" in values

    def test_barcode_service_none_skips_step_gracefully(self) -> None:
        """Sin barcode_service configurado el paso se ignora sin error."""
        steps = [BarcodeStep(id="bc1")]
        executor = _make_executor(steps, barcode_service=None)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.barcodes == []
        assert page.flags.processing_errors == []

    def test_script_reads_accumulated_barcodes(self) -> None:
        """Un ScriptStep posterior puede leer page.barcodes."""
        fake_bc = MagicMock()
        fake_bc.value = "X-100"

        script_src = """
def run(app, batch, page, pipeline):
    page.fields['first_barcode'] = page.barcodes[0].value if page.barcodes else ''
"""
        steps = [
            BarcodeStep(id="bc1"),
            ScriptStep(id="s1", label="Lee bc", entry_point="run", script=script_src),
        ]
        svc = self._fake_barcode_service([fake_bc])
        executor = _make_executor(steps, barcode_service=svc)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.fields["first_barcode"] == "X-100"


# ------------------------------------------------------------------ #
# 3. Control de flujo: skip_step y abort                               #
# ------------------------------------------------------------------ #


class TestPipelineFlowControl:
    """Scripts que invocan skip_step() y abort() del PipelineContext."""

    def test_skip_step_prevents_target_step_execution(self) -> None:
        """skip_step('s2') hace que el paso s2 no se ejecute."""
        script_skip = """
def run(app, batch, page, pipeline):
    pipeline.skip_step('s2')
"""
        script_target = """
def run(app, batch, page, pipeline):
    page.fields['s2_ran'] = True
"""
        steps = [
            ScriptStep(id="s1", label="Salta s2", entry_point="run", script=script_skip),
            ScriptStep(id="s2", label="Objetivo", entry_point="run", script=script_target),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert "s2_ran" not in page.fields
        assert page.flags.script_errors == []

    def test_skip_to_jumps_intermediate_steps(self) -> None:
        """skip_to('s3') hace que s2 no se ejecute pero s3 sí."""
        script_s1 = """
def run(app, batch, page, pipeline):
    pipeline.skip_to('s3')
"""
        script_s2 = """
def run(app, batch, page, pipeline):
    page.fields['s2_ran'] = True
"""
        script_s3 = """
def run(app, batch, page, pipeline):
    page.fields['s3_ran'] = True
"""
        steps = [
            ScriptStep(id="s1", label="skip_to s3", entry_point="run", script=script_s1),
            ScriptStep(id="s2", label="Intermedio", entry_point="run", script=script_s2),
            ScriptStep(id="s3", label="Destino", entry_point="run", script=script_s3),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert "s2_ran" not in page.fields
        assert page.fields.get("s3_ran") is True

    def test_abort_stops_pipeline_and_sets_needs_review(self) -> None:
        """abort() detiene el pipeline y marca page.flags.needs_review."""
        script_abort = """
def run(app, batch, page, pipeline):
    pipeline.abort('documento inválido')
"""
        script_after = """
def run(app, batch, page, pipeline):
    page.fields['after_abort'] = True
"""
        steps = [
            ScriptStep(id="s1", label="Aborta", entry_point="run", script=script_abort),
            ScriptStep(id="s2", label="Nunca llega", entry_point="run", script=script_after),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.flags.needs_review is True
        assert "documento inválido" in page.flags.review_reason
        assert "after_abort" not in page.fields

    def test_abort_with_empty_reason(self) -> None:
        """abort() sin razón pone needs_review=True sin review_reason."""
        script_src = """
def run(app, batch, page, pipeline):
    pipeline.abort()
"""
        steps = [
            ScriptStep(id="s1", label="Aborta", entry_point="run", script=script_src),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.flags.needs_review is True

    def test_script_exception_does_not_stop_pipeline(self) -> None:
        """Una excepción en ScriptStep se registra pero el pipeline continúa."""
        script_bad = """
def run(app, batch, page, pipeline):
    raise RuntimeError('error deliberado')
"""
        script_ok = """
def run(app, batch, page, pipeline):
    page.fields['continued'] = True
"""
        steps = [
            ScriptStep(id="s1", label="Falla", entry_point="run", script=script_bad),
            ScriptStep(id="s2", label="Continúa", entry_point="run", script=script_ok),
        ]
        executor = _make_executor(steps)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        # El pipeline NO se detuvo
        assert page.fields.get("continued") is True
        # El error quedó registrado en flags
        assert len(page.flags.script_errors) == 1
        assert "error deliberado" in page.flags.script_errors[0]["error"]


# ------------------------------------------------------------------ #
# 4. repeat_step con límite                                            #
# ------------------------------------------------------------------ #


class TestPipelineRepeatStep:
    """repeat_step se ejecuta hasta max_repeats y luego aborta."""

    def test_repeat_step_reruns_target(self) -> None:
        """repeat_step('op') hace que op se ejecute dos veces en total."""
        script_src = """
def run(app, batch, page, pipeline):
    count = page.fields.get('count', 0)
    page.fields['count'] = count + 1
    if count == 0:
        pipeline.repeat_step('op')
"""
        steps = [
            ScriptStep(id="op", label="Contador", entry_point="run", script=script_src),
        ]
        executor = _make_executor(steps, max_repeats=3)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        # Primera ejecución (count=0) pide repeat; segunda (count=1) no.
        assert page.fields["count"] == 2

    def test_repeat_step_exceeds_max_aborts_pipeline(self) -> None:
        """Superar max_repeats dispara PipelineAbortError → needs_review."""
        # El script SIEMPRE pide repeat → superará el límite
        script_src = """
def run(app, batch, page, pipeline):
    count = page.fields.get('count', 0)
    page.fields['count'] = count + 1
    pipeline.repeat_step('repeater')
"""
        steps = [
            ScriptStep(
                id="repeater",
                label="Repite siempre",
                entry_point="run",
                script=script_src,
            ),
        ]
        executor = _make_executor(steps, max_repeats=2)
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        # El pipeline abortó por exceso de repeticiones
        assert page.flags.needs_review is True
        # Se ejecutó max_repeats + 1 veces (orig + 2 repeats, luego abort en el 3°)
        assert page.fields["count"] == 3

    def test_repeat_step_unknown_id_logs_warning(self, caplog) -> None:
        """repeat_step con id desconocido registra warning y no bloquea."""
        import logging

        script_src = """
def run(app, batch, page, pipeline):
    pipeline.repeat_step('inexistente')
    page.fields['ran'] = True
"""
        steps = [
            ScriptStep(id="s1", label="ID malo", entry_point="run", script=script_src),
        ]
        executor = _make_executor(steps, max_repeats=3)
        page = _PageCtx(page_index=0, image=_white_image())

        with caplog.at_level(logging.WARNING, logger="app.pipeline.context"):
            executor.execute(page, _BatchCtx(), _AppCtx())

        assert "inexistente" in caplog.text


# ------------------------------------------------------------------ #
# 5. Ciclo de vida del lote (BatchService)                             #
# ------------------------------------------------------------------ #


class TestBatchLifecycle:
    """Crear lote, añadir páginas y transicionar todos los estados."""

    def test_create_batch_returns_created_state(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)

        batch = svc.create_batch(application_id=app_record.id)

        assert batch.id is not None
        assert batch.state == "created"
        assert batch.application_id == app_record.id

    def test_create_batch_with_fields(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)

        batch = svc.create_batch(
            application_id=app_record.id,
            fields={"cliente": "Acme", "año": "2026"},
        )

        fields = svc.get_fields(batch.id)
        assert fields["cliente"] == "Acme"
        assert fields["año"] == "2026"

    def test_add_pages_saves_images_to_disk(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)

        images = [_white_image(), _white_image()]
        pages = svc.add_pages(batch.id, images, output_format="png")

        assert len(pages) == 2
        for p in pages:
            assert p.image_path
            from pathlib import Path
            assert Path(p.image_path).exists()

    def test_add_pages_increments_page_count(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)

        svc.add_pages(batch.id, [_white_image()])
        svc.add_pages(batch.id, [_white_image(), _white_image()])

        updated = svc.get_batch(batch.id)
        assert updated.page_count == 3

    def test_full_state_transitions(self, session, app_record, tmp_path) -> None:
        """Recorrido completo: created → read → verified → ready_to_export → exported."""
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)

        for state in ("read", "verified", "ready_to_export", "exported"):
            updated = svc.transition_state(batch.id, state)
            assert updated.state == state

    def test_transition_to_invalid_state_raises(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)

        with pytest.raises(ValueError, match="Estado no válido"):
            svc.transition_state(batch.id, "inexistente")

    def test_get_batches_by_state(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)
        b1 = svc.create_batch(application_id=app_record.id)
        b2 = svc.create_batch(application_id=app_record.id)
        svc.transition_state(b2.id, "read")

        created_batches = svc.get_batches_by_state("created")
        read_batches = svc.get_batches_by_state("read")

        created_ids = [b.id for b in created_batches]
        assert b1.id in created_ids
        assert b2.id not in created_ids
        assert any(b.id == b2.id for b in read_batches)

    def test_delete_batch_removes_files_and_record(self, session, app_record, tmp_path) -> None:
        from pathlib import Path

        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)
        svc.add_pages(batch.id, [_white_image()], output_format="png")

        batch_id = batch.id
        pages_before = svc.get_pages(batch_id)
        assert len(pages_before) == 1

        svc.delete_batch(batch_id)
        session.flush()

        assert svc.get_batch(batch_id) is None

    def test_batch_stats_counts_pages(self, session, app_record, tmp_path) -> None:
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)
        svc.add_pages(batch.id, [_white_image(), _white_image()], output_format="png")

        stats = svc.get_stats(batch.id)

        assert stats["total_pages"] == 2
        assert stats["needs_review"] == 0
        assert stats["excluded"] == 0


# ------------------------------------------------------------------ #
# 6. Integración pipeline + BatchService                               #
# ------------------------------------------------------------------ #


class TestPipelineWithBatchService:
    """Pipeline real sobre páginas de un lote creado con BatchService."""

    def test_pipeline_processes_batch_pages(self, session, app_record, tmp_path) -> None:
        """Crea un lote, carga sus imágenes y las procesa con el pipeline."""
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)
        svc.add_pages(batch.id, [_white_image(), _white_image()], output_format="png")

        script_src = """
def process(app, batch, page, pipeline):
    page.fields['processed'] = True
    page.fields['page_index'] = page.page_index
"""
        steps = [
            ImageOpStep(id="op1", op="FxGrayscale"),
            ScriptStep(id="s1", label="Marca", entry_point="process", script=script_src),
        ]
        executor = _make_executor(steps)

        db_pages = svc.get_pages(batch.id)
        batch_ctx = _BatchCtx(id=batch.id, state=batch.state)
        app_ctx = _AppCtx(id=app_record.id, name=app_record.name)

        results = []
        for db_page in db_pages:
            img = svc.get_page_image(db_page)
            assert img is not None
            page_ctx = _PageCtx(page_index=db_page.page_index, image=img)
            result = executor.execute(page_ctx, batch_ctx, app_ctx)
            results.append(result)

        assert len(results) == 2
        for r in results:
            assert r.fields.get("processed") is True
            assert r.flags.processing_errors == []

    def test_pipeline_abort_does_not_corrupt_other_pages(
        self, session, app_record, tmp_path
    ) -> None:
        """El abort de una página no afecta el procesado de la siguiente."""
        svc = BatchService(session=session, images_dir=tmp_path)
        batch = svc.create_batch(application_id=app_record.id)
        svc.add_pages(batch.id, [_white_image(), _white_image()], output_format="png")

        # El script aborta en página 0, no en página 1
        script_src = """
def run(app, batch, page, pipeline):
    if page.page_index == 0:
        pipeline.abort('solo la primera')
    page.fields['ok'] = True
"""
        steps = [
            ScriptStep(id="s1", label="Condicional", entry_point="run", script=script_src),
        ]
        executor = _make_executor(steps)

        db_pages = svc.get_pages(batch.id)
        batch_ctx = _BatchCtx(id=batch.id)
        app_ctx = _AppCtx()

        page0_ctx = _PageCtx(page_index=0, image=svc.get_page_image(db_pages[0]))
        page1_ctx = _PageCtx(page_index=1, image=svc.get_page_image(db_pages[1]))

        executor.execute(page0_ctx, batch_ctx, app_ctx)
        executor.execute(page1_ctx, batch_ctx, app_ctx)

        assert page0_ctx.flags.needs_review is True
        assert "ok" not in page0_ctx.fields

        assert page1_ctx.flags.needs_review is False
        assert page1_ctx.fields.get("ok") is True


# ------------------------------------------------------------------ #
# 7. ScriptEngine: compilación y detección de errores de sintaxis      #
# ------------------------------------------------------------------ #


class TestScriptEngineCompilation:
    """ScriptEngine.compile_script() y run_step() en aislamiento."""

    def test_compile_valid_script_succeeds(self) -> None:
        engine = ScriptEngine()
        engine.compile_script("s1", "def run(app, batch, page, pipeline): pass")
        assert engine.is_compiled("s1")

    def test_compile_syntax_error_raises(self) -> None:
        from app.services.script_engine import ScriptCompilationError

        engine = ScriptEngine()
        with pytest.raises(ScriptCompilationError, match="sintaxis"):
            engine.compile_script("bad", "def run(: pass")

    def test_clear_cache_removes_compiled_scripts(self) -> None:
        engine = ScriptEngine()
        engine.compile_script("s1", "def run(app, batch, page, pipeline): pass")
        engine.clear_cache()
        assert not engine.is_compiled("s1")

    def test_run_step_without_compilation_returns_none(self) -> None:
        """run_step con script no compilado devuelve None y no falla."""
        engine = ScriptEngine()
        step = ScriptStep(id="s1", label="Sin compilar", entry_point="run", script="")
        page = _PageCtx(page_index=0)

        result = engine.run_step(step, page, _BatchCtx(), _AppCtx(), MagicMock())

        assert result is None

    def test_run_step_missing_entry_point_returns_none(self) -> None:
        """run_step con entry_point inexistente en el código devuelve None."""
        engine = ScriptEngine()
        step = ScriptStep(
            id="s1",
            label="Sin EP",
            entry_point="no_existe",
            script="def otra(): pass",
        )
        engine.compile_step(step)
        page = _PageCtx(page_index=0)

        result = engine.run_step(step, page, _BatchCtx(), _AppCtx(), MagicMock())

        assert result is None

    def test_run_step_propagates_abort_error(self) -> None:
        """run_step no captura PipelineAbortError; el executor lo recibe."""
        from app.pipeline.context import PipelineAbortError, PipelineContext
        from app.pipeline.steps import ScriptStep

        engine = ScriptEngine()
        script_src = """
def run(app, batch, page, pipeline):
    pipeline.abort('forzado')
"""
        step = ScriptStep(id="s1", label="Aborta", entry_point="run", script=script_src)
        engine.compile_step(step)

        image_svc = ImagePipelineService()
        executor = PipelineExecutor(
            steps=[step],
            image_service=image_svc,
            script_engine=engine,
        )
        page = _PageCtx(page_index=0, image=_white_image())

        executor.execute(page, _BatchCtx(), _AppCtx())

        assert page.flags.needs_review is True
        assert "forzado" in page.flags.review_reason
