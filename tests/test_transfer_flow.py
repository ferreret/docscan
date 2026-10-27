"""Tests del flujo de transferencia compartido (app/services/transfer_flow.py).

Usan el ScriptEngine real: el bug que corrige este flujo estaba justo en la
frontera entre el motor (que traga la excepción) y quien interpreta su
resultado, y un mock del motor lo habría ocultado.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np

from app.pipeline.page_context import AppContext, BatchContext
from app.services.script_engine import ScriptEngine
from app.services.transfer_flow import (
    TransferPage,
    execute_transfer,
    missing_required_fields,
    validate_before_transfer,
)
from app.services.transfer_service import (
    TransferConfig,
    TransferResult,
    TransferService,
)


def _engine(**events: str) -> ScriptEngine:
    engine = ScriptEngine()
    for name, source in events.items():
        engine.compile_script(name, source)
    return engine


def _ctx() -> dict:
    return {"app": AppContext(id=1, name="App"), "batch": BatchContext(id=7)}


def _page(tmp_path: Path, index: int = 0) -> dict:
    path = tmp_path / f"p{index}.png"
    cv2.imwrite(str(path), np.full((20, 20, 3), 255, np.uint8))
    return {
        "image_path": str(path),
        "page_index": index,
        "fields": {"nhc": f"H{index}"},
        "ocr_text": "",
        "first_barcode": f"B{index}",
    }


# ------------------------------------------------------------------
# Validación previa
# ------------------------------------------------------------------


class TestValidacionPrevia:
    def test_campos_obligatorios_vacios(self) -> None:
        defs = [
            {"label": "NHC", "type": "texto", "required": True},
            {"label": "Opcional", "type": "texto", "required": False},
            {"name": "Fecha", "type": "Fecha", "required": True},
        ]
        assert missing_required_fields(defs, {"NHC": " ", "Fecha": ""}) == [
            "NHC",
            "Fecha",
        ]
        assert missing_required_fields(defs, {"NHC": "1", "Fecha": "01/01/2026"}) == []

    def test_obligatorio_vacio_nombra_el_campo(self) -> None:
        reason = validate_before_transfer(
            script_engine=None,
            contexts=_ctx(),
            fields_def=[{"label": "NHC", "type": "texto", "required": True}],
            batch_fields={},
        )
        assert reason is not None and "NHC" in reason

    def test_sin_evento_permite(self) -> None:
        assert (
            validate_before_transfer(
                script_engine=_engine(),
                contexts=_ctx(),
                fields_def=[],
                batch_fields={},
            )
            is None
        )

    def test_evento_que_devuelve_false_bloquea(self) -> None:
        engine = _engine(
            on_transfer_validate="def on_transfer_validate(app, batch):\n    return False\n"
        )
        reason = validate_before_transfer(
            script_engine=engine, contexts=_ctx(), fields_def=[], batch_fields={}
        )
        assert reason == "La validación previa ha rechazado la transferencia"

    def test_evento_que_lanza_bloquea(self) -> None:
        """Antes, la excepción se tragaba y la validación dejaba pasar todo."""
        engine = _engine(
            on_transfer_validate=(
                "def on_transfer_validate(app, batch):\n"
                "    raise ValueError('falta el número de factura')\n"
            )
        )
        reason = validate_before_transfer(
            script_engine=engine, contexts=_ctx(), fields_def=[], batch_fields={}
        )
        assert reason is not None
        assert "falta el número de factura" in reason

    def test_firma_con_argumento_inexistente_bloquea(self) -> None:
        """La firma que documentaba el README (con `page`) ya no pasa en silencio."""
        engine = _engine(
            on_transfer_validate=(
                "def on_transfer_validate(app, batch, page):\n    return True\n"
            )
        )
        reason = validate_before_transfer(
            script_engine=engine, contexts=_ctx(), fields_def=[], batch_fields={}
        )
        assert reason is not None and "TypeError" in reason


# ------------------------------------------------------------------
# Ejecución
# ------------------------------------------------------------------


class TestEjecucion:
    def _config(self, tmp_path: Path, **kw) -> TransferConfig:
        return TransferConfig(destination=str(tmp_path / "out"), **kw)

    def test_avanzado_que_lanza_hace_fallar(self, tmp_path: Path) -> None:
        engine = _engine(
            on_transfer_advanced=(
                "def on_transfer_advanced(app, batch, pages=None, result=None):\n"
                "    raise RuntimeError('LIS caído')\n"
            )
        )
        result = execute_transfer(
            transfer_service=TransferService(),
            config=self._config(tmp_path),
            pages=[_page(tmp_path)],
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts=_ctx(),
        )
        assert result.success is False
        assert any("LIS caído" in e for e in result.errors)

    def test_avanzado_que_devuelve_false_hace_fallar(self, tmp_path: Path) -> None:
        engine = _engine(
            on_transfer_advanced=(
                "def on_transfer_advanced(app, batch, pages=None, result=None):\n"
                "    return False\n"
            )
        )
        result = execute_transfer(
            transfer_service=TransferService(),
            config=self._config(tmp_path, standard_enabled=False),
            pages=[_page(tmp_path)],
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts=_ctx(),
        )
        assert result.success is False

    def test_avanzado_corre_despues_de_la_estandar_y_recibe_todo(
        self, tmp_path: Path
    ) -> None:
        """Mismo contrato en Workbench y worker: pages y result."""
        engine = _engine(
            on_transfer_advanced=(
                "def on_transfer_advanced(app, batch, pages=None, result=None):\n"
                "    assert result.files_transferred == 2\n"
                "    assert [p.first_barcode for p in pages] == ['B0', 'B1']\n"
                "    assert pages[1].fields['nhc'] == 'H1'\n"
                "    assert pages[0].image is not None\n"
                "    return True\n"
            )
        )
        result = execute_transfer(
            transfer_service=TransferService(),
            config=self._config(tmp_path),
            pages=[_page(tmp_path, 0), _page(tmp_path, 1)],
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts=_ctx(),
        )
        assert result.success is True, result.errors
        assert result.files_transferred == 2

    def test_firma_antigua_con_result_funciona(self, tmp_path: Path) -> None:
        """La firma (app, batch, result) que enseñaba el asistente ya recibe result."""
        engine = _engine(
            on_transfer_advanced=(
                "def on_transfer_advanced(app, batch, result):\n"
                "    return result.success\n"
            )
        )
        result = execute_transfer(
            transfer_service=TransferService(),
            config=self._config(tmp_path),
            pages=[_page(tmp_path)],
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts=_ctx(),
        )
        assert result.success is True

    def test_fallo_estandar_no_ejecuta_avanzado(self, tmp_path: Path) -> None:
        service = MagicMock()
        service.transfer.return_value = TransferResult(success=False, errors=["x"])
        engine = MagicMock()
        engine.is_compiled.return_value = True
        result = execute_transfer(
            transfer_service=service,
            config=self._config(tmp_path),
            pages=[],
            batch_fields={},
            batch_id=7,
            script_engine=engine,
        )
        assert result.success is False
        engine.run_event_checked.assert_not_called()

    def test_nada_configurado_falla_con_motivo(self, tmp_path: Path) -> None:
        result = execute_transfer(
            transfer_service=TransferService(),
            config=self._config(tmp_path, standard_enabled=False),
            pages=[],
            batch_fields={},
            batch_id=7,
            script_engine=_engine(),
        )
        assert result.success is False and result.errors

    def test_estandar_sin_destino_falla_con_motivo(self) -> None:
        result = execute_transfer(
            transfer_service=TransferService(),
            config=TransferConfig(destination=""),
            pages=[],
            batch_fields={},
            batch_id=7,
        )
        assert result.success is False
        assert "destino" in result.errors[0]


class TestTransferPage:
    def test_imagen_bajo_demanda(self, tmp_path: Path) -> None:
        page = TransferPage.from_dict(_page(tmp_path))
        assert page._image_loaded is False
        assert page.image is not None
        assert page._image_loaded is True

    def test_imagen_inexistente_es_none(self, tmp_path: Path) -> None:
        page = TransferPage(image_path=str(tmp_path / "no.png"))
        assert page.image is None
