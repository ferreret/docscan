"""Tests de app/services/event_config.py: casilla «Activado» de los eventos.

Un evento pausado (``{"script", "enabled": false}``) conserva el código pero
no se compila, así que no corre en el Workbench, el worker ni transfer_flow.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services.event_config import (
    active_event_sources,
    event_enabled,
    event_entry_point,
    event_source,
    has_code,
    make_event_entry,
    parse_events,
)

CODE = "def on_app_start(app, batch):\n    pass\n"


class TestLectura:
    def test_las_dos_formas(self):
        assert event_source(CODE) == CODE
        assert event_source({"script": CODE}) == CODE
        assert event_source(None) == ""
        assert event_source({"script": 3}) == ""

    def test_activado_por_defecto(self):
        assert event_enabled(CODE)
        assert event_enabled({"script": CODE})
        assert event_enabled({"script": CODE, "enabled": True})
        assert not event_enabled({"script": CODE, "enabled": False})

    def test_entry_point(self):
        assert event_entry_point("on_x", CODE) == "on_x"
        assert event_entry_point("on_x", {"entry_point": "f"}) == "f"
        assert event_entry_point("on_x", {"entry_point": ""}) == "on_x"

    def test_has_code(self):
        assert has_code(CODE)
        assert has_code({"script": CODE, "enabled": False})
        assert not has_code("  \n")
        assert not has_code({"enabled": True})

    @pytest.mark.parametrize("raw", ["", None, "no es json", "[1, 2]"])
    def test_parse_events_tolerante(self, raw):
        assert parse_events(raw) == {}

    def test_active_event_sources_salta_pausados_y_vacios(self):
        events = {
            "on_app_start": CODE,
            "on_app_end": {"script": CODE, "enabled": False},
            "on_import": "",
            "on_scan_complete": {"script": CODE, "entry_point": "f"},
        }
        assert active_event_sources(json.dumps(events)) == {
            "on_app_start": CODE,
            "on_scan_complete": CODE,
        }


class TestEscritura:
    def test_activado_se_guarda_como_texto(self):
        assert make_event_entry(None, CODE, True) == CODE
        assert make_event_entry(CODE, CODE, True) == CODE

    def test_pausado_se_guarda_como_dict(self):
        assert make_event_entry(CODE, CODE, False) == {
            "script": CODE,
            "enabled": False,
        }

    def test_dict_conserva_sus_claves(self):
        prev = {"script": "old", "entry_point": "f", "enabled": False}
        assert make_event_entry(prev, CODE, True) == {
            "script": CODE,
            "entry_point": "f",
        }
        assert make_event_entry(prev, CODE, False)["enabled"] is False


class TestEventoPausadoNoCorre:
    def test_worker_no_compila_el_evento_pausado(self):
        from app.services.script_engine import ScriptEngine
        from docscan_worker.worker_main import _compile_lifecycle_events

        app = SimpleNamespace(
            events_json=json.dumps(
                {
                    "on_app_start": {"script": CODE, "enabled": False},
                    "on_transfer_validate": (
                        "def on_transfer_validate(app, batch):\n    return False\n"
                    ),
                }
            )
        )
        engine = ScriptEngine()
        result = _compile_lifecycle_events(app, engine)
        assert result == {"on_transfer_validate": "on_transfer_validate"}
        assert not engine.is_compiled("on_app_start")

    def test_transfer_flow_no_valida_con_un_evento_pausado(self):
        """on_transfer_validate pausado: la validación no lo ejecuta."""
        from app.services.script_engine import ScriptEngine
        from app.services.transfer_flow import validate_before_transfer
        from docscan_worker.worker_main import _compile_lifecycle_events

        rechaza = "def on_transfer_validate(app, batch):\n    return False\n"
        engine = ScriptEngine()
        app = SimpleNamespace(
            events_json=json.dumps(
                {"on_transfer_validate": {"script": rechaza, "enabled": False}}
            )
        )
        _compile_lifecycle_events(app, engine)
        motivo = validate_before_transfer(
            script_engine=engine,
            contexts={"app": SimpleNamespace(), "batch": SimpleNamespace()},
            fields_def=[],
            batch_fields={},
        )
        assert motivo is None

        # Activado, el mismo script sí rechaza
        app.events_json = json.dumps({"on_transfer_validate": rechaza})
        engine = ScriptEngine()
        _compile_lifecycle_events(app, engine)
        motivo = validate_before_transfer(
            script_engine=engine,
            contexts={"app": SimpleNamespace(), "batch": SimpleNamespace()},
            fields_def=[],
            batch_fields={},
        )
        assert motivo is not None
