"""Tests del separador de documento (lote 6, paridad FlexibarNET10).

Cubren el documento lógico (``split_documents``), la condición de separador
del ``BarcodeStep``, la leyenda legacy de simbologías, la detección en el
executor, el estado del ``PageContext`` y la migración.
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from app.models.document import split_documents
from app.pipeline import separator
from app.pipeline.executor import PipelineExecutor
from app.pipeline.page_context import (
    BarcodeResult,
    PageContext,
    persist_separator,
    separator_state,
)
from app.pipeline.serializer import deserialize, serialize
from app.pipeline.steps import BarcodeStep, ScriptStep
from app.services.image_pipeline import ImagePipelineService
from app.services.script_engine import ScriptEngine
from app.utils.symbology_numbers import symbology_prefix
from app.workers.recognition_worker import AppContext, BatchContext


def _page(index: int, sep: bool = False, value: str = "") -> dict:
    return {"page_index": index, "is_separator": sep, "separator_value": value}


# ------------------------------------------------------------------
# Documento lógico
# ------------------------------------------------------------------


class TestSplitDocuments:
    def test_sin_paginas(self):
        assert split_documents([]) == []

    def test_sin_separadores_es_un_documento_implicito(self):
        docs = split_documents([_page(0), _page(1), _page(2)])
        assert len(docs) == 1
        assert docs[0].is_implicit
        assert docs[0].separator_value == ""
        assert [p["page_index"] for p in docs[0].pages] == [0, 1, 2]

    def test_tramos_entre_separadores(self):
        pages = [
            _page(0, True, "A"),
            _page(1),
            _page(2, True, "B"),
            _page(3),
            _page(4),
        ]
        docs = split_documents(pages)
        assert [d.index for d in docs] == [1, 2]
        assert [d.separator_value for d in docs] == ["A", "B"]
        assert [len(d.pages) for d in docs] == [2, 3]
        assert not docs[0].is_implicit

    def test_paginas_antes_del_primer_separador(self):
        docs = split_documents([_page(0), _page(1, True, "A"), _page(2)])
        assert len(docs) == 2
        assert docs[0].is_implicit
        assert docs[1].separator_value == "A"

    def test_cada_pagina_separadora_es_un_documento(self):
        docs = split_documents([_page(i, True, f"V{i}") for i in range(3)])
        assert [d.separator_value for d in docs] == ["V0", "V1", "V2"]

    def test_campos_del_documento_son_los_de_la_separadora(self):
        sep = {**_page(0, True, "A"), "fields": {"tipo": "factura"}}
        docs = split_documents([sep, _page(1)])
        assert docs[0].fields == {"tipo": "factura"}

    def test_admite_objetos(self):
        pages = [SimpleNamespace(page_index=0, is_separator=True, separator_value="X")]
        assert split_documents(pages)[0].separator_value == "X"


# ------------------------------------------------------------------
# Leyenda legacy y condición de separador
# ------------------------------------------------------------------


class TestSymbologyNumbers:
    @pytest.mark.parametrize(
        ("symbology", "expected"),
        [("Code39", "01"), ("Code128", "02"), ("ITF", "10"), ("QR", "22")],
    )
    def test_numeros_de_flexibar(self, symbology, expected):
        assert symbology_prefix(symbology) == expected

    def test_desconocida_es_cero(self):
        assert symbology_prefix("Nada") == "00"


def _bc(value: str, symbology: str = "Code128") -> BarcodeResult:
    return BarcodeResult(value=value, symbology=symbology)


class TestSeparatorMatcher:
    def test_regex_con_numero_de_simbologia(self):
        # Caso Arnau: ^(02|10) = Code128 o Interleaved 2 of 5
        step = BarcodeStep(
            id="b",
            separator_enabled=True,
            separator_by="regex",
            separator_regex="^(02|10)",
            separator_regex_include_symbology=True,
        )
        assert separator.matches(step, _bc("12345678", "Code128"))
        assert separator.matches(step, _bc("123456789", "ITF"))
        assert not separator.matches(step, _bc("12345678", "Code39"))

    def test_regex_sin_simbologia(self):
        step = BarcodeStep(id="b", separator_by="regex", separator_regex=r"^FAC-\d+$")
        assert separator.matches(step, _bc("FAC-12"))
        assert not separator.matches(step, _bc("ALB-12"))

    def test_regex_invalida_no_casa(self):
        step = BarcodeStep(id="b", separator_by="regex", separator_regex="(")
        assert not separator.matches(step, _bc("x"))

    def test_por_simbologia(self):
        step = BarcodeStep(
            id="b", separator_by="symbology", separator_symbology="code39"
        )
        assert separator.matches(step, _bc("1", "Code39"))
        assert not separator.matches(step, _bc("1", "Code128"))

    def test_valor_fijo(self):
        step = BarcodeStep(
            id="b", separator_by="fixed_value", separator_fixed_value="SEP"
        )
        assert separator.matches(step, _bc("SEP"))
        assert not separator.matches(step, _bc("SEPX"))

    def test_valor_del_primer_codigo_que_casa(self):
        step = BarcodeStep(id="b", separator_by="regex", separator_regex="^9")
        assert (
            separator.find_matching_value(step, [_bc("1"), _bc("91"), _bc("92")])
            == "91"
        )
        assert separator.find_matching_value(step, [_bc("1")]) is None

    def test_sugerencia_manual(self):
        step = BarcodeStep(
            id="b",
            separator_by="regex",
            separator_regex="^9",
            separator_default_value="DEF",
        )
        assert separator.suggest_manual_value(step, [_bc("1"), _bc("91")]) == "91"
        assert separator.suggest_manual_value(step, [_bc("1")]) == "1"
        assert separator.suggest_manual_value(step, []) == "DEF"
        assert separator.suggest_manual_value(None, []) == ""

    def test_sugerencia_manual_no_propone_el_valor_fijo(self):
        step = BarcodeStep(
            id="b", separator_by="fixed_value", separator_fixed_value="SEP"
        )
        assert separator.suggest_manual_value(step, [_bc("SEP")]) == "SEP"
        step.separator_default_value = "X"
        assert separator.suggest_manual_value(step, []) == "X"

    def test_validacion_manual(self):
        step = BarcodeStep(id="b", separator_manual_regex=r"^\d{8,9}$")
        assert separator.manual_value_error(step, "12345678") is None
        assert separator.manual_value_error(step, "1234") is not None
        assert separator.manual_value_error(step, "") is None  # vacío admitido
        assert separator.manual_value_error(None, "loquesea") is None


class TestSerializer:
    def test_ida_y_vuelta_con_claves_de_flexibar(self):
        step = BarcodeStep(
            id="barcode",
            symbologies=["Code128", "ITF"],
            separator_enabled=True,
            separator_by="regex",
            separator_regex="^(02|10)",
            separator_regex_include_symbology=True,
            separator_manual_regex=r"^\d{8,9}$",
            separator_default_value="0",
        )
        raw = json.loads(serialize([step]))[0]
        assert raw["separator_enabled"] is True
        assert raw["separator_by"] == "regex"
        assert raw["separator_regex"] == "^(02|10)"
        assert raw["separator_regex_include_symbology"] is True
        assert raw["separator_manual_regex"] == r"^\d{8,9}$"
        back = deserialize(serialize([step]))[0]
        assert back == step

    def test_pipeline_antiguo_sin_campos_de_separador(self):
        step = deserialize('[{"id": "b", "type": "barcode"}]')[0]
        assert step.separator_enabled is False
        assert step.separator_by == "regex"


# ------------------------------------------------------------------
# Detección en el executor
# ------------------------------------------------------------------


class _FakeBarcodes:
    """Servicio de barcodes que devuelve lo configurado por paso."""

    def __init__(self, by_step: dict[str, list[BarcodeResult]]):
        self._by_step = by_step

    def read(self, *, step_id: str, **_kwargs):
        return [
            BarcodeResult(value=b.value, symbology=b.symbology, step_id=step_id)
            for b in self._by_step.get(step_id, [])
        ]


def _run(steps, barcodes, page=None, scripts=()):
    engine = ScriptEngine()
    for s in steps:
        if isinstance(s, ScriptStep):
            engine.compile_step(s)
    executor = PipelineExecutor(
        steps=steps,
        image_service=ImagePipelineService(),
        script_engine=engine,
        barcode_service=_FakeBarcodes(barcodes),
    )
    page = page or PageContext(page_index=0, image=np.zeros((10, 10, 3), np.uint8))
    executor.execute(page=page, batch=BatchContext(), app=AppContext())
    return page


def _sep_step(step_id: str, regex: str) -> BarcodeStep:
    return BarcodeStep(
        id=step_id,
        separator_enabled=True,
        separator_by="regex",
        separator_regex=regex,
        separator_regex_include_symbology=True,
    )


class TestExecutorDetection:
    def test_marca_la_pagina_con_el_valor(self):
        page = _run([_sep_step("b", "^02")], {"b": [_bc("12345678")]})
        assert page.is_separator
        assert page.separator_value == "12345678"
        assert page.separator_decided
        # El barcode no recibe rol
        assert page.barcodes[0].role == ""

    def test_autoritativo_desmarca_la_marca_manual(self):
        page = PageContext(
            page_index=0,
            image=np.zeros((10, 10, 3), np.uint8),
            is_separator=True,
            separator_value="MANUAL",
        )
        page = _run([_sep_step("b", "^02")], {"b": [_bc("x", "Code39")]}, page)
        assert not page.is_separator
        assert page.separator_value == ""
        assert page.separator_decided

    def test_sin_deteccion_conserva_la_marca(self):
        page = PageContext(
            page_index=0,
            image=np.zeros((10, 10, 3), np.uint8),
            is_separator=True,
            separator_value="MANUAL",
        )
        page = _run([BarcodeStep(id="b")], {"b": [_bc("1")]}, page)
        assert page.is_separator
        assert page.separator_value == "MANUAL"
        assert not page.separator_decided

    def test_casa_cualquiera_de_varios_pasos(self):
        steps = [_sep_step("b1", "^02"), _sep_step("b2", "^01")]
        page = _run(steps, {"b1": [_bc("A")], "b2": [_bc("B", "Code128")]})
        # b1 casa y b2 no: sigue siendo separador con el valor de b1
        assert page.is_separator
        assert page.separator_value == "A"

    def test_un_script_posterior_tiene_la_ultima_palabra(self):
        script = ScriptStep(
            id="s",
            entry_point="run",
            script=(
                "def run(app, batch, page, pipeline):\n"
                "    page.is_separator = False\n"
                "    page.separator_value = ''\n"
            ),
        )
        page = _run([_sep_step("b", "^02"), script], {"b": [_bc("1")]})
        assert not page.is_separator


class TestPageContextState:
    def test_inicializar_no_cuenta_como_decision(self):
        page = PageContext(page_index=0, is_separator=True, separator_value="A")
        assert not page.separator_decided

    def test_persistir_solo_si_se_decidio(self):
        db = SimpleNamespace(is_separator=True, separator_value="A")
        ctx = PageContext(page_index=0, **separator_state(db))
        persist_separator(ctx, db)
        assert db.is_separator and db.separator_value == "A"
        ctx.is_separator = False
        ctx.separator_value = ""
        persist_separator(ctx, db)
        assert not db.is_separator and db.separator_value == ""

    def test_valor_recortado_a_500(self):
        db = SimpleNamespace(is_separator=False, separator_value="")
        ctx = PageContext(page_index=0)
        ctx.is_separator = True
        ctx.separator_value = "x" * 600
        persist_separator(ctx, db)
        assert len(db.separator_value) == 500


# ------------------------------------------------------------------
# Migración
# ------------------------------------------------------------------


def test_migracion_marca_las_paginas_con_rol_separator(tmp_path):
    """Los lotes antiguos con ``role="separator"`` conservan su aspecto."""
    from alembic import command
    from sqlalchemy import create_engine

    from app.db.database import (
        Base,
        _alembic_config,
        create_db_engine,
        run_migrations,
    )
    from app.models.application import Application
    from app.models.barcode import Barcode
    from app.models.batch import Batch
    from app.models.operation_history import OperationHistory
    from app.models.page import Page
    from app.models.template import Template

    db = tmp_path / "m.db"
    e = create_engine(f"sqlite:///{db.as_posix()}")
    tables = [
        m.__table__
        for m in (Application, Batch, Page, Barcode, Template, OperationHistory)
    ]
    Base.metadata.create_all(e, tables=tables)
    with e.begin() as c:
        # Esquema de la revisión anterior: sin las columnas nuevas.
        c.exec_driver_sql("ALTER TABLE pages DROP COLUMN separator_value")
        c.exec_driver_sql("ALTER TABLE pages DROP COLUMN is_separator")
        c.exec_driver_sql("PRAGMA foreign_keys=OFF")
        c.exec_driver_sql(
            "INSERT INTO pages (id, batch_id, page_index, image_path, ocr_text, "
            "index_fields_json, needs_review, review_reason, is_blank, "
            "is_excluded, pipeline_processed, processing_errors_json, "
            "script_errors_json) VALUES "
            "(1, 1, 0, '', '', '{}', 0, '', 0, 0, 0, '[]', '[]'), "
            "(2, 1, 1, '', '', '{}', 0, '', 0, 0, 0, '[]', '[]')"
        )
        c.exec_driver_sql(
            "INSERT INTO barcodes (page_id, value, symbology, engine, step_id, "
            "quality, pos_x, pos_y, pos_w, pos_h, role) VALUES "
            "(1, 'FAC-1', 'Code128', 'motor1', 'b', 0, 0, 0, 0, 0, 'separator'), "
            "(2, 'X', 'Code128', 'motor1', 'b', 0, 0, 0, 0, 0, '')"
        )
    with e.connect() as conn:
        cfg = _alembic_config()
        cfg.attributes["connection"] = conn
        command.stamp(cfg, "b4e2a7c9d1f3")
    e.dispose()

    engine = create_db_engine(db_path=db)
    run_migrations(engine)
    engine.dispose()

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, is_separator, separator_value FROM pages ORDER BY id"
    ).fetchall()
    con.close()
    assert rows == [(1, 1, "FAC-1"), (2, 0, "")]
