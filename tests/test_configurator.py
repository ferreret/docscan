"""Tests del configurador de aplicación."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QModelIndex, Qt
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.pipeline.steps import (
    ImageOpStep,
    BarcodeStep,
    OcrStep,
    ScriptStep,
)
from app.pipeline.serializer import serialize
from app.ui.configurator.app_configurator import AppConfigurator
from app.ui.configurator.tabs.tab_general import GeneralTab
from app.ui.configurator.tabs.tab_pipeline import PipelineTab, _step_display_text
from app.ui.configurator.tabs.tab_events import EventsTab
from app.ui.configurator.tabs.tab_transfer import TransferTab
from app.ui.configurator.tabs.tab_batch_fields import BatchFieldsTab
from app.ui.configurator.step_dialogs.image_op_dialog import ImageOpDialog
from app.ui.configurator.step_dialogs.barcode_step_dialog import BarcodeStepDialog
from app.ui.configurator.step_dialogs.ocr_step_dialog import OcrStepDialog
from app.ui.configurator.step_dialogs.script_step_dialog import ScriptStepDialog


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def sample_app(session_factory) -> Application:
    with session_factory() as session:
        app = Application(
            name="Test App",
            description="Descripción test",
            pipeline_json=serialize(
                [
                    ImageOpStep(id="s1", op="AutoDeskew"),
                    BarcodeStep(id="s2", engine="motor2", symbologies=["QR"]),
                ]
            ),
            events_json=json.dumps(
                {
                    "on_app_start": "def on_app_start(app, batch):\n    pass",
                }
            ),
            transfer_json=json.dumps(
                {
                    "mode": "pdf",
                    "destination": "/tmp/output",
                    "pdf_dpi": 300,
                }
            ),
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        session.expunge(app)
        return app


# ------------------------------------------------------------------
# Tab General
# ------------------------------------------------------------------


class TestGeneralTab:
    def test_loads_values(self, qtbot, sample_app):
        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._name_edit.text() == "Test App"
        assert tab._active_check.isChecked()

    def test_apply_to(self, qtbot, sample_app):
        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        tab._name_edit.setText("Renamed App")
        tab.apply_to(sample_app)
        assert sample_app.name == "Renamed App"


# ------------------------------------------------------------------
# Tab Pipeline
# ------------------------------------------------------------------


class TestPipelineTab:
    def test_loads_steps(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._list.count() == 2
        steps = tab.get_steps()
        assert len(steps) == 2
        assert isinstance(steps[0], ImageOpStep)

    def test_toggle_step(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.setCurrentRow(0)
        tab._on_toggle()
        steps = tab.get_steps()
        assert not steps[0].enabled

    def test_delete_step(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.setCurrentRow(0)
        tab._on_delete()
        assert tab._list.count() == 1

    def test_move_up(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.setCurrentRow(1)
        tab._on_move_up()
        steps = tab.get_steps()
        assert isinstance(steps[0], BarcodeStep)
        assert isinstance(steps[1], ImageOpStep)

    def test_move_down(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.setCurrentRow(0)
        tab._on_move_down()
        steps = tab.get_steps()
        assert isinstance(steps[0], BarcodeStep)

    def test_apply_serializes(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._on_toggle()  # No selection, no-op
        tab.apply_to(sample_app)
        assert sample_app.pipeline_json != "[]"

    def test_cada_fila_tiene_casilla_e_icono(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        for i, step in enumerate(tab.get_steps()):
            item = tab._list.item(i)
            assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
            assert (item.checkState() == Qt.CheckState.Checked) == step.enabled
            assert not item.icon().isNull()

    def test_la_casilla_desactiva_el_paso(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.item(1).setCheckState(Qt.CheckState.Unchecked)
        assert not tab.get_steps()[1].enabled
        assert tab.get_steps()[0].enabled
        tab.apply_to(sample_app)
        assert '"enabled": false' in sample_app.pipeline_json
        tab._list.item(1).setCheckState(Qt.CheckState.Checked)
        assert tab.get_steps()[1].enabled

    def test_paso_desactivado_se_ve_atenuado(self, qtbot, sample_app):
        from app.ui.palette import color

        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        tab._list.setCurrentRow(0)
        tab._on_toggle()
        item = tab._list.item(0)
        assert item.checkState() == Qt.CheckState.Unchecked
        assert item.foreground().color().name() == color("text_disabled")

    def test_arrastrar_reordena_los_pasos(self, qtbot, sample_app):
        """Antes la lista se reordenaba al arrastrar pero _steps no: se perdía."""
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        primero, segundo = tab.get_steps()
        # Lo que hace QListWidget al soltar un arrastre interno
        model = tab._list.model()
        assert model.moveRows(QModelIndex(), 1, 1, QModelIndex(), 0)
        assert tab.get_steps() == [segundo, primero]
        tab.apply_to(sample_app)
        assert sample_app.pipeline_json.index(
            '"barcode"'
        ) < sample_app.pipeline_json.index('"image_op"')

    def test_sin_boton_on_off(self, qtbot, sample_app):
        tab = PipelineTab(sample_app)
        qtbot.addWidget(tab)
        assert not hasattr(tab, "_btn_toggle")
        assert not tab._btn_up.icon().isNull()

    def test_empty_pipeline(self, qtbot):
        app = Application(name="Empty", pipeline_json="[]")
        tab = PipelineTab(app)
        qtbot.addWidget(tab)
        assert tab._list.count() == 0


class TestStepDisplayText:
    def test_image_op(self):
        step = ImageOpStep(id="s1", op="AutoDeskew")
        text = _step_display_text(step)
        assert "Imagen" in text
        assert "AutoDeskew" in text

    def test_barcode(self):
        step = BarcodeStep(id="s1", engine="motor2", symbologies=["QR", "DataMatrix"])
        text = _step_display_text(step)
        assert "Barcode" in text
        assert "motor2" in text

    def test_script(self):
        step = ScriptStep(id="s1", label="Mi script")
        text = _step_display_text(step)
        assert "Script" in text
        assert "Mi script" in text

    def test_sin_marca_de_texto(self):
        """El estado activo va en la casilla de la fila, no en el texto."""
        step = ImageOpStep(id="s1", op="Crop", enabled=False)
        assert _step_display_text(step) == "Imagen: Crop"


# ------------------------------------------------------------------
# Tab Events
# ------------------------------------------------------------------


class TestEventsTab:
    def test_loads_events(self, qtbot, sample_app):
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        # El primer evento (on_app_start) debería tener código
        assert "def on_app_start" in tab._code_edit.toPlainText()

    def test_apply_saves_current(self, qtbot, sample_app):
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        tab.set_event_code(
            "on_app_start", "def on_app_start(app, batch):\n    print('hi')"
        )
        tab.apply_to(sample_app)
        events = json.loads(sample_app.events_json)
        assert "print('hi')" in events["on_app_start"]

    def test_empty_event_removed(self, qtbot, sample_app):
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        tab.set_event_code("on_app_start", "")
        tab.apply_to(sample_app)
        events = json.loads(sample_app.events_json)
        assert "on_app_start" not in events

    def test_event_names_includes_on_batch_loaded_and_on_page_changed(self):
        """v0.1.1: ambos eventos deben aparecer en el catálogo."""
        from app.ui.configurator.tabs.tab_events import (
            EVENT_DESCRIPTIONS,
            EVENT_NAMES,
            EVENT_TITLES,
        )

        assert "on_batch_loaded" in EVENT_NAMES
        assert "on_page_changed" in EVENT_NAMES
        descriptions = EVENT_DESCRIPTIONS()
        assert descriptions.get("on_batch_loaded")
        assert descriptions.get("on_page_changed")
        # Todos los eventos tienen nombre legible
        assert set(EVENT_TITLES()) == set(EVENT_NAMES)

    def test_placeholder_changes_with_selected_event(self, qtbot, sample_app):
        """v0.1.1: el placeholder del editor debe reflejar la firma del
        evento seleccionado. Antes estaba hardcoded a ``on_app_start``
        para todos los eventos.
        """
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        # Al cargar, el primer evento es on_app_start.
        assert "on_app_start" in tab._code_edit.placeholderText()
        tab.select_event("on_page_changed")
        ph = tab._code_edit.placeholderText()
        assert "def on_page_changed(app, batch, page, page_index):" in ph
        tab.select_event("on_key_event")
        ph2 = tab._code_edit.placeholderText()
        assert "def on_key_event(app, batch, key):" in ph2

    def test_placeholder_signatures_for_v0_1_1_events(self, qtbot, sample_app):
        """v0.1.1: las firmas de on_batch_loaded y on_page_changed están
        en EVENT_SIGNATURES (regresión: antes faltaban y caían a la de
        on_app_start)."""
        from app.services._assistant_constants import EVENT_SIGNATURES

        assert "on_batch_loaded" in EVENT_SIGNATURES
        assert "def on_batch_loaded(app, batch):" in EVENT_SIGNATURES["on_batch_loaded"]
        assert "on_page_changed" in EVENT_SIGNATURES
        assert (
            "def on_page_changed(app, batch, page, page_index):"
            in EVENT_SIGNATURES["on_page_changed"]
        )


class TestEventsTabParidad:
    """Lista con estado, casilla «Activado» y diálogo «Editar script…»."""

    def _tab(self, qtbot, events: dict) -> EventsTab:
        app = Application(name="E", events_json=json.dumps(events))
        tab = EventsTab(app)
        qtbot.addWidget(tab)
        return tab

    def test_lista_en_lugar_de_combo(self, qtbot, sample_app):
        from app.ui.configurator.tabs.tab_events import EVENT_NAMES

        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        assert not hasattr(tab, "_event_combo")
        assert tab._event_list.count() == len(EVENT_NAMES)

    def test_estados_vacio_activo_y_pausado(self, qtbot):
        from app.ui.configurator.tabs.tab_events import (
            STATE_ACTIVE,
            STATE_EMPTY,
            STATE_PAUSED,
        )

        tab = self._tab(
            qtbot,
            {
                "on_app_start": "def on_app_start(app, batch):\n    pass",
                "on_app_end": {
                    "script": "def on_app_end(app, batch):\n    pass",
                    "enabled": False,
                },
            },
        )
        assert tab.state_of("on_app_start") == STATE_ACTIVE
        assert tab.state_of("on_app_end") == STATE_PAUSED
        assert tab.state_of("on_import") == STATE_EMPTY
        assert tab._rows["on_app_end"].state == STATE_PAUSED
        assert tab._rows["on_app_end"]._pill.text() == "PAUSADO"

    def test_desactivar_guarda_dict_y_reactivar_vuelve_a_texto(self, qtbot):
        code = "def on_app_start(app, batch):\n    pass"
        tab = self._tab(qtbot, {"on_app_start": code})
        tab.select_event("on_app_start")
        tab._chk_enabled.setChecked(False)
        out = Application(name="R")
        tab.apply_to(out)
        assert json.loads(out.events_json)["on_app_start"] == {
            "script": code,
            "enabled": False,
        }
        tab._chk_enabled.setChecked(True)
        tab.apply_to(out)
        assert json.loads(out.events_json)["on_app_start"] == code

    def test_conserva_claves_que_no_edita(self, qtbot):
        tab = self._tab(
            qtbot,
            {
                "on_app_start": {
                    "script": "def inicio(app, batch):\n    pass",
                    "entry_point": "inicio",
                },
                "evento_desconocido": "x = 1",
            },
        )
        out = Application(name="R")
        tab.apply_to(out)
        events = json.loads(out.events_json)
        assert events["on_app_start"]["entry_point"] == "inicio"
        assert "enabled" not in events["on_app_start"]
        assert events["evento_desconocido"] == "x = 1"

    def test_casilla_inhabilitada_sin_codigo(self, qtbot):
        tab = self._tab(qtbot, {})
        tab.select_event("on_import")
        assert not tab._chk_enabled.isEnabled()
        tab.set_event_code("on_import", "def on_import(app, batch):\n    pass")
        assert tab._chk_enabled.isEnabled()

    def test_editar_script_abre_el_dialogo(self, qtbot, monkeypatch):
        from app.ui.configurator import event_script_dialog

        tab = self._tab(qtbot, {})
        tab.select_event("on_transfer_validate")
        nuevo = "def on_transfer_validate(app, batch):\n    return True"
        monkeypatch.setattr(
            event_script_dialog.EventScriptDialog, "exec", lambda self: 1
        )
        monkeypatch.setattr(
            event_script_dialog.EventScriptDialog, "code", lambda self: nuevo
        )
        tab._btn_edit.click()
        assert tab._code_edit.toPlainText() == nuevo
        assert tab._code_edit.isReadOnly()


class TestEventScriptDialog:
    def test_variables_de_la_firma_y_del_motor(self):
        from app.ui.configurator.event_script_dialog import available_variables

        names = [n for n, _ in available_variables("on_transfer_validate")]
        assert names[:4] == ["app", "batch", "pages", "documents"]
        assert {"log", "http", "re", "json", "datetime", "Path"} <= set(names)
        assert [n for n, _ in available_variables("init_global")][0] == "log"

    def test_dialogo_con_editor_y_panel(self, qtbot):
        from app.ui.configurator.event_script_dialog import EventScriptDialog
        from app.ui.widgets.code_editor import CodeEditor

        dlg = EventScriptDialog(
            "on_page_changed", "Al cambiar de página", "x = 1", "placeholder"
        )
        qtbot.addWidget(dlg)
        assert isinstance(dlg._code_edit, CodeEditor)
        assert dlg.code() == "x = 1"
        assert "page_index" in dlg._variable_names


# ------------------------------------------------------------------
# Tab Transfer
# ------------------------------------------------------------------


class TestTransferTab:
    def test_loads_config(self, qtbot, sample_app):
        tab = TransferTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._mode_combo.currentText() == "pdf"
        assert tab._dest_edit.text() == "/tmp/output"
        assert tab._pdf_dpi.value() == 300

    def test_apply_to(self, qtbot, sample_app):
        tab = TransferTab(sample_app)
        qtbot.addWidget(tab)
        tab._mode_combo.setCurrentText("csv")
        tab._csv_fields_edit.setText("ref, tipo")
        tab.apply_to(sample_app)
        config = json.loads(sample_app.transfer_json)
        assert config["mode"] == "csv"
        assert config["csv_fields"] == ["ref", "tipo"]

    def test_documentos_y_script_de_nombre_ida_y_vuelta(self, qtbot, sample_app):
        """Lote 6: las claves nuevas no se pierden al guardar."""
        sample_app.transfer_json = json.dumps(
            {
                "mode": "tiff",
                "destination": "/tmp/out",
                "grouping": "document",
                "separator_page": "exclude",
                "name_mode": "script",
                "file_name_script": "def file_name(page, document, batch, app):\n    return 'x'\n",
                "output_tiff_compression": "group4",
                "collision_policy": "merge",
            }
        )
        tab = TransferTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._mode_combo.currentText() == "tiff"
        assert tab._grouping_combo.currentData() == "document"
        assert tab._separator_page_combo.currentData() == "exclude"
        assert tab._name_mode_combo.currentData() == "script"
        tab.apply_to(sample_app)
        config = json.loads(sample_app.transfer_json)
        assert config["mode"] == "tiff"
        assert config["grouping"] == "document"
        assert config["separator_page"] == "exclude"
        assert config["name_mode"] == "script"
        assert "return 'x'" in config["file_name_script"]
        assert config["output_tiff_compression"] == "group4"
        assert config["collision_policy"] == "merge"

    def test_script_de_nombre_roto_no_se_guarda(self):
        from app.services.script_engine import find_script_errors

        transfer = json.dumps(
            {"name_mode": "script", "file_name_script": "def file_name(:\n"}
        )
        errors = find_script_errors("[]", "{}", transfer)
        assert errors and "Script de nombre de fichero" in errors[0]
        # En modo patrón el script guardado no se comprueba
        transfer = json.dumps(
            {"name_mode": "pattern", "file_name_script": "def file_name(:\n"}
        )
        assert find_script_errors("[]", "{}", transfer) == []


# ------------------------------------------------------------------
# Step Dialogs
# ------------------------------------------------------------------


class TestImageOpDialog:
    def test_get_step(self, qtbot):
        step = ImageOpStep(id="s1")
        dialog = ImageOpDialog(step)
        qtbot.addWidget(dialog)
        dialog._op_combo.setCurrentText("FxGrayscale")
        dialog._params_edit.setText("threshold=128")
        result = dialog.get_step()
        assert result.op == "FxGrayscale"
        assert result.params == {"threshold": 128}


class TestBarcodeStepDialog:
    def test_get_step(self, qtbot):
        step = BarcodeStep(id="s1")
        dialog = BarcodeStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._engine_combo.setCurrentText("motor2")
        dialog._symb_checks["QR"].setChecked(True)
        dialog._symb_checks["Code128"].setChecked(True)
        result = dialog.get_step()
        assert result.engine == "motor2"
        assert set(result.symbologies) == {"QR", "Code128"}

    def test_casillas_por_familia(self, qtbot):
        from app.ui.configurator.step_dialogs.barcode_step_dialog import (
            SYMBOLOGY_FAMILIES,
        )

        dialog = BarcodeStepDialog(BarcodeStep(id="s", symbologies=["ITF", "QR"]))
        qtbot.addWidget(dialog)
        assert [f for f, _ in SYMBOLOGY_FAMILIES] == ["1D lineal", "EAN/UPC", "2D"]
        assert dialog._symb_checks["ITF"].isChecked()
        assert dialog._symb_checks["QR"].isChecked()
        assert not dialog._symb_checks["Code39"].isChecked()

    def test_sin_tocar_nada_el_paso_no_cambia(self, qtbot):
        step = BarcodeStep(
            id="s",
            engine="motor2",
            symbologies=["Code128", "QR"],
            regex=r"^\d+$",
            regex_include_symbology=True,
            orientations=["horizontal", "diagonal"],
            quality_threshold=0.5,
            window=(10, 20, 300, 400),
        )
        before = BarcodeStep(**{**step.__dict__})
        dialog = BarcodeStepDialog(step)
        qtbot.addWidget(dialog)
        after = dialog.get_step()
        assert after == before

    def test_simbologia_desconocida_se_conserva(self, qtbot):
        dialog = BarcodeStepDialog(BarcodeStep(id="s", symbologies=["Code 11", "QR"]))
        qtbot.addWidget(dialog)
        assert set(dialog.get_step().symbologies) == {"Code 11", "QR"}

    def test_ninguna_marcada_es_todas(self, qtbot):
        dialog = BarcodeStepDialog(BarcodeStep(id="s"))
        qtbot.addWidget(dialog)
        assert dialog.get_step().symbologies == []

    def test_region_a_cero_es_pagina_completa(self, qtbot):
        dialog = BarcodeStepDialog(BarcodeStep(id="s", window=(1, 2, 3, 4)))
        qtbot.addWidget(dialog)
        for spin in dialog._window_spins:
            spin.setValue(0)
        assert dialog.get_step().window is None

    def test_leyenda_visible_bajo_la_regex(self, qtbot):
        from PySide6.QtWidgets import QLabel

        dialog = BarcodeStepDialog(BarcodeStep(id="s"))
        qtbot.addWidget(dialog)
        legends = dialog.findChildren(QLabel, "symbologyLegend")
        assert len(legends) == 2  # Filtrado y separador por regex
        assert all("Code128 = 02" in lbl.text() for lbl in legends)

    def test_avanzado_muestra_el_json(self, qtbot):
        dialog = BarcodeStepDialog(BarcodeStep(id="s"))
        qtbot.addWidget(dialog)
        dialog._regex_edit.setText("^FAC")
        assert json.loads(dialog._json_view.toPlainText())["regex"] == "^FAC"
        # La vista previa no toca el paso hasta aceptar
        assert dialog._step.regex == ""


class TestOcrStepDialog:
    def test_get_step(self, qtbot):
        step = OcrStep(id="s1")
        dialog = OcrStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._engine_combo.setCurrentText("easyocr")
        dialog._langs_edit.setText("es, en")
        result = dialog.get_step()
        assert result.engine == "easyocr"
        assert result.languages == ["es", "en"]


class TestScriptStepDialog:
    def test_get_step(self, qtbot):
        step = ScriptStep(id="s1")
        dialog = ScriptStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._label_edit.setText("Mi script")
        dialog._entry_edit.setText("my_func")
        dialog._code_edit.setPlainText(
            "def my_func(app, batch, page, pipeline):\n    pass"
        )
        result = dialog.get_step()
        assert result.label == "Mi script"
        assert result.entry_point == "my_func"
        assert "def my_func" in result.script


# ------------------------------------------------------------------
# AppConfigurator (integración)
# ------------------------------------------------------------------


class TestBatchFieldsTab:
    def _tab(self, qtbot, fields: list) -> BatchFieldsTab:
        app = Application(name="F", batch_fields_json=json.dumps(fields))
        tab = BatchFieldsTab(app)
        qtbot.addWidget(tab)
        return tab

    @staticmethod
    def _labels(tab) -> list[str]:
        return [f["label"] for f in tab._fields]

    @staticmethod
    def _saved(tab) -> list[dict]:
        out = Application(name="R")
        tab.apply_to(out)
        return json.loads(out.batch_fields_json)

    def test_empty_fields(self, qtbot, sample_app):
        sample_app.batch_fields_json = "[]"
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._list.count() == 0
        # Sin selección se ve «Sin campo seleccionado»
        assert tab._detail_stack.currentIndex() == 0

    def test_loads_existing_fields(self, qtbot):
        tab = self._tab(
            qtbot,
            [
                {"label": "Expediente", "type": "texto", "required": True},
                {
                    "label": "Prioridad",
                    "type": "lista",
                    "required": False,
                    "config": {"values": ["Alta", "Media", "Baja"]},
                },
                {
                    "label": "Páginas",
                    "type": "numérico",
                    "required": False,
                    "config": {"min": 1, "max": 500, "step": 1},
                },
            ],
        )
        assert tab._list.count() == 3
        # Se abre con el primero seleccionado en el detalle
        assert tab._label_edit.text() == "Expediente"
        assert tab._type_combo.currentText() == "texto"
        assert tab._required_check.isChecked()

        tab._list.setCurrentRow(1)
        assert tab._label_edit.text() == "Prioridad"
        assert "Alta" in tab._list_values.text()

        tab._list.setCurrentRow(2)
        assert tab._num_min.value() == 1
        assert tab._num_max.value() == 500

    def test_fila_con_nombre_tipo_y_obligatorio(self, qtbot):
        from app.ui.configurator.tabs.tab_batch_fields import field_summary

        assert field_summary({"label": "NIF", "type": "texto", "required": True}) == (
            "NIF",
            "texto · obligatorio",
        )
        assert field_summary({"label": "", "type": "fecha"}) == (
            "(sin nombre)",
            "fecha",
        )

    def test_add_field(self, qtbot):
        tab = self._tab(qtbot, [])
        tab._add_empty_row()
        assert tab._list.count() == 1
        assert tab._list.currentRow() == 0
        assert tab._type_combo.currentText() == "texto"

    def test_change_type_updates_config_widget(self, qtbot):
        tab = self._tab(qtbot, [{"label": "Campo1", "type": "texto"}])
        tab._type_combo.setCurrentText("numérico")
        assert tab._config_stack.currentIndex() == tab._config_pages["numérico"]
        assert tab._fields[0]["config"] == {"min": 0, "max": 100, "step": 1}
        tab._type_combo.setCurrentText("lista")
        assert tab._config_stack.currentIndex() == tab._config_pages["lista"]
        # Al cambiar de tipo no quedan claves del tipo anterior
        assert tab._fields[0]["config"] == {"values": []}
        tab._type_combo.setCurrentText("texto")
        assert "config" not in tab._fields[0]

    def test_apply_to_serializes_all_types(self, qtbot):
        fields = [
            {"label": "Nombre", "type": "texto", "required": True},
            {
                "label": "Estado",
                "type": "lista",
                "required": False,
                "config": {"values": ["Abierto", "Cerrado"]},
            },
            {
                "label": "Cantidad",
                "type": "numérico",
                "required": True,
                "config": {"min": 0, "max": 999, "step": 5},
            },
        ]
        tab = self._tab(qtbot, fields)
        # Recorrer los campos en el detalle no cambia nada
        for row in range(3):
            tab._list.setCurrentRow(row)
        assert self._saved(tab) == fields

    def test_descripcion_y_valor_por_defecto(self, qtbot):
        tab = self._tab(qtbot, [{"label": "Data", "type": "fecha"}])
        tab._default_edit.setText("01/01/2026")
        tab._description_edit.setPlainText("Data del lot. Buida = avui.")
        saved = self._saved(tab)[0]
        assert saved["default"] == "01/01/2026"
        assert saved["description"] == "Data del lot. Buida = avui."
        # Vaciarlos quita la clave en lugar de guardar ""
        tab._default_edit.setText("")
        tab._description_edit.setPlainText("")
        saved = self._saved(tab)[0]
        assert "default" not in saved and "description" not in saved

    def test_apply_to_no_descarta_claves(self, qtbot):
        """Regresión: apply_to rehacía cada campo con 4 claves y perdía el resto."""
        fields = [
            {
                "label": "Data",
                "type": "fecha",
                "config": {"format": "dd/MM/yyyy", "extra": 1},
                "required": False,
                "description": "Data del lot",
                "default": "01/01/2026",
                "clave_futura": {"x": [1, 2]},
            }
        ]
        tab = self._tab(qtbot, fields)
        tab._required_check.setChecked(True)  # editar otra clave
        saved = self._saved(tab)[0]
        assert saved["clave_futura"] == {"x": [1, 2]}
        assert saved["description"] == "Data del lot"
        assert saved["default"] == "01/01/2026"
        assert saved["config"] == {"format": "dd/MM/yyyy", "extra": 1}
        assert saved["required"] is True

    def test_empty_label_rows_skipped_on_apply(self, qtbot):
        tab = self._tab(qtbot, [])
        tab._add_empty_row()  # Nombre vacío
        tab._add_empty_row()
        tab._label_edit.setText("Campo Real")
        saved = self._saved(tab)
        assert [f["label"] for f in saved] == ["Campo Real"]

    def test_remove_row(self, qtbot):
        tab = self._tab(
            qtbot,
            [{"label": n, "type": "texto", "required": False} for n in "ABC"],
        )
        tab._remove_row(1)  # Eliminar "B"
        assert tab._list.count() == 2
        assert self._labels(tab) == ["A", "C"]
        assert tab._label_edit.text() == "C"

    def test_boton_eliminar_quita_el_seleccionado(self, qtbot):
        tab = self._tab(qtbot, [{"label": "A", "type": "texto"}])
        tab._btn_remove.click()
        assert tab._list.count() == 0
        assert tab._detail_stack.currentIndex() == 0
        assert not tab._btn_remove.isEnabled()

    def test_move_row_down(self, qtbot):
        tab = self._tab(
            qtbot,
            [
                {"label": "Primero", "type": "texto", "required": False},
                {
                    "label": "Segundo",
                    "type": "lista",
                    "required": True,
                    "config": {"values": ["X", "Y"]},
                },
            ],
        )
        tab._move_row(0, 1)  # Mover "Primero" abajo
        assert self._labels(tab) == ["Segundo", "Primero"]
        assert tab._list.currentRow() == 1
        assert tab._label_edit.text() == "Primero"

    def test_move_row_up(self, qtbot):
        tab = self._tab(
            qtbot,
            [
                {"label": "A", "type": "texto", "required": False},
                {
                    "label": "B",
                    "type": "numérico",
                    "required": True,
                    "config": {"min": 0, "max": 10, "step": 1},
                },
            ],
        )
        tab._move_row(1, -1)  # Mover "B" arriba
        assert self._labels(tab) == ["B", "A"]
        assert self._saved(tab)[0]["config"] == {"min": 0, "max": 10, "step": 1}

    def test_move_row_boundary_no_crash(self, qtbot):
        tab = self._tab(qtbot, [{"label": "Solo", "type": "texto"}])
        tab._move_row(0, -1)  # No puede subir más
        tab._move_row(0, 1)  # No puede bajar más
        assert tab._list.count() == 1

    def test_required_checkbox_state(self, qtbot):
        tab = self._tab(
            qtbot,
            [
                {"label": "Req", "type": "texto", "required": True},
                {"label": "Opt", "type": "texto", "required": False},
            ],
        )
        assert tab._required_check.isChecked() is True
        tab._list.setCurrentRow(1)
        assert tab._required_check.isChecked() is False


# ------------------------------------------------------------------
# App Configurator
# ------------------------------------------------------------------


class TestAppConfigurator:
    def test_creates_with_tabs(self, qtbot, sample_app, session_factory):
        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        assert dialog._tabs.count() == 7
        assert dialog.windowTitle().startswith("Configurar")

    def test_grupo_sugiere_los_existentes_y_se_guarda(
        self, qtbot, sample_app, session_factory
    ):
        with session_factory() as session:
            session.add_all(
                [
                    Application(name="A", group="hospital Arnau"),
                    Application(name="B", group="Ayuntamiento"),
                    Application(name="C", group="Ayuntamiento"),
                ]
            )
            session.commit()
        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        combo = dialog._tab_general._group_combo
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "Ayuntamiento",
            "hospital Arnau",
        ]
        combo.setEditText("Ayuntamiento")
        dialog._on_save()
        with session_factory() as session:
            saved = session.get(Application, sample_app.id)
            assert saved.group == "Ayuntamiento"

    def test_no_guarda_si_un_evento_no_compila(
        self, qtbot, sample_app, session_factory
    ):
        """Paridad FlexibarNET10 v1.20: el Configurador rechaza scripts rotos."""
        from unittest.mock import patch

        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        tab = dialog._tab_events
        assert tab._current_event == "on_app_start"
        tab.set_event_code("on_app_start", "def on_app_start(app, batch:\n")
        with patch("app.ui.configurator.app_configurator.QMessageBox.warning") as aviso:
            dialog._on_save()
        aviso.assert_called_once()
        assert "on_app_start" in aviso.call_args.args[2]
        assert dialog.result() == 0  # no se aceptó el diálogo


class TestFindScriptErrors:
    def test_detecta_pipeline_y_eventos(self):
        import json

        from app.services.script_engine import find_script_errors

        pipeline = json.dumps(
            [
                {
                    "type": "script",
                    "id": "s1",
                    "label": "Separar",
                    "entry_point": "f",
                    "script": "def f(:\n",
                }
            ]
        )
        events = json.dumps(
            {
                "on_app_start": "def on_app_start(app, batch):\n    pass\n",
                "verification_panel": {"script": "class X(:\n"},
            }
        )
        errors = find_script_errors(pipeline, events)
        assert len(errors) == 2
        assert any("Separar" in e for e in errors)
        assert any("verification_panel" in e for e in errors)

    def test_sin_errores(self):
        from app.services.script_engine import find_script_errors

        assert find_script_errors("[]", "{}") == []


class TestPestanasDelWorkbench:
    """Configurador → General → «Pestañas del Workbench» (paridad Flexibar)."""

    def test_lista_con_las_cinco_entradas_y_guardado(self, qtbot, sample_app):
        import json

        from app.ui.configurator.tabs.tab_general import GeneralTab

        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        lista = tab._layout_list
        from PySide6.QtCore import Qt

        ids = [
            lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lista.count())
        ]
        assert ids == ["barcodes", "campos", "verificacion", "ocr", "log"]

        # Ocultar OCR y subir Log por encima de él
        lista.item(3).setCheckState(Qt.CheckState.Unchecked)
        lista.setCurrentRow(4)
        tab._move_layout_entry(-1)
        tab._hide_add_barcode.setChecked(True)
        tab.apply_to(sample_app)

        guardado = json.loads(sample_app.workbench_layout_json)
        assert [e["id"] for e in guardado] == [
            "barcodes",
            "campos",
            "verificacion",
            "log",
            "ocr",
        ]
        assert next(e for e in guardado if e["id"] == "ocr")["visible"] is False
        assert sample_app.hide_add_barcode_button is True

    def test_los_paneles_fijos_no_se_reordenan(self, qtbot, sample_app):
        from app.ui.configurator.tabs.tab_general import GeneralTab

        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        tab._layout_list.setCurrentRow(1)  # «Campos de lote»
        assert not tab._btn_layout_up.isEnabled()
        assert not tab._btn_layout_down.isEnabled()
        tab._layout_list.setCurrentRow(2)  # primera pestaña: no sube
        assert not tab._btn_layout_up.isEnabled()
        assert tab._btn_layout_down.isEnabled()


class TestBarcodeStepDialogSeparador:
    def test_separador_ida_y_vuelta(self, qtbot):
        step = BarcodeStep(
            id="b",
            separator_enabled=True,
            separator_by="regex",
            separator_regex="^(02|10)",
            separator_regex_include_symbology=True,
            separator_manual_regex=r"^\d{8}$",
        )
        dialog = BarcodeStepDialog(step)
        qtbot.addWidget(dialog)
        assert dialog._sep_auto.isChecked()
        assert dialog._sep_regex.isEnabled()
        assert not dialog._sep_fixed.isEnabled()
        out = dialog.get_step()
        assert out.separator_enabled
        assert out.separator_regex == "^(02|10)"
        assert out.separator_regex_include_symbology
        assert out.separator_manual_regex == r"^\d{8}$"

    def test_desactivar_la_deteccion(self, qtbot):
        step = BarcodeStep(id="b", separator_enabled=True)
        dialog = BarcodeStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._sep_auto.setChecked(False)
        dialog._sep_mode.setCurrentIndex(dialog._sep_mode.findData("fixed_value"))
        out = dialog.get_step()
        assert not out.separator_enabled
        assert out.separator_by == "fixed_value"

    def test_solo_se_ve_el_campo_de_la_condicion(self, qtbot):
        dialog = BarcodeStepDialog(BarcodeStep(id="b", separator_by="symbology"))
        qtbot.addWidget(dialog)
        form = dialog._sep_form
        assert form.isRowVisible(dialog._sep_symbology)
        assert not form.isRowVisible(dialog._sep_regex)
        assert not form.isRowVisible(dialog._sep_fixed)
        dialog._sep_mode.setCurrentIndex(dialog._sep_mode.findData("regex"))
        assert form.isRowVisible(dialog._sep_regex)
        assert form.isRowVisible(dialog._sep_legend)
        assert not form.isRowVisible(dialog._sep_symbology)

    def test_marca_manual_independiente_de_la_deteccion(self, qtbot):
        """Bloque «Marca manual»: editable aunque no haya detección automática."""
        dialog = BarcodeStepDialog(BarcodeStep(id="b", separator_enabled=False))
        qtbot.addWidget(dialog)
        assert not dialog._sep_auto_body.isEnabled()
        assert dialog._sep_manual_regex.isEnabled()
        dialog._sep_manual_regex.setText(r"^\d{6}$")
        dialog._sep_default.setText("000000")
        out = dialog.get_step()
        assert out.separator_manual_regex == r"^\d{6}$"
        assert out.separator_default_value == "000000"


class TestGeneralTabParidad:
    """Opciones de FlexibarNET10 que siembran las Apps del Arnau."""

    def test_dialogo_del_escaner_y_color_ida_y_vuelta(self, qtbot, sample_app):
        sample_app.show_scanner_ui = True
        sample_app.icon_accent = "blue"
        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._show_scanner_ui.isChecked()
        assert tab._accent_combo.currentData() == "blue"
        tab._accent_combo.setCurrentIndex(0)  # automático
        tab._show_scanner_ui.setChecked(False)
        tab.apply_to(sample_app)
        assert sample_app.icon_accent == ""
        assert sample_app.show_scanner_ui is False

    def test_grupo_ida_y_vuelta(self, qtbot, sample_app):
        sample_app.group = "Hospital Arnau de Vilanova"
        tab = GeneralTab(sample_app, ["Ayuntamiento", "Hospital Arnau de Vilanova"])
        qtbot.addWidget(tab)
        combo = tab._group_combo
        assert combo.isEditable()
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "Ayuntamiento",
            "Hospital Arnau de Vilanova",
        ]
        assert combo.currentText() == "Hospital Arnau de Vilanova"
        # Escribir un grupo nuevo lo crea; los espacios de los extremos sobran
        combo.setEditText("  Clínica  ")
        tab.apply_to(sample_app)
        assert sample_app.group == "Clínica"
        # Vacío = sin grupo
        combo.setEditText("")
        tab.apply_to(sample_app)
        assert sample_app.group == ""

    def test_sin_grupo_el_combo_queda_vacio(self, qtbot, sample_app):
        sample_app.group = ""
        tab = GeneralTab(sample_app, ["Ayuntamiento"])
        qtbot.addWidget(tab)
        assert tab._group_combo.currentText() == ""
        tab.apply_to(sample_app)
        assert sample_app.group == ""

    def test_un_backend_de_otra_plataforma_se_conserva(self, qtbot, sample_app):
        sample_app.scanner_backend = "twain"
        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        tab.apply_to(sample_app)
        assert sample_app.scanner_backend == "twain"


class TestScriptDeNombreEnVSCode:
    """El script de nombre se puede editar en VS Code, como los eventos."""

    def test_boton_solo_en_modo_script(self, qtbot, sample_app):
        from unittest.mock import patch

        sample_app.transfer_json = json.dumps({"mode": "tiff", "name_mode": "pattern"})
        with patch(
            "app.ui.configurator.tabs.tab_transfer.detect_editor",
            return_value="/usr/bin/code",
        ):
            tab = TransferTab(sample_app)
            qtbot.addWidget(tab)
            tab.show()
            assert not tab._vscode_bar.isVisible()
            tab._name_mode_combo.setCurrentIndex(
                tab._name_mode_combo.findData("script")
            )
            assert tab._vscode_bar.isVisible()

    def test_lo_que_vuelve_de_vscode_queda_en_el_editor(self, qtbot, sample_app):
        tab = TransferTab(sample_app)
        qtbot.addWidget(tab)
        tab._on_editor_done(
            "def file_name(page, document, batch, app):\n    return 'x'\n"
        )
        assert "return 'x'" in tab._name_script_edit.toPlainText()
        tab._on_editor_done(None)  # cancelado: no se toca
        assert "return 'x'" in tab._name_script_edit.toPlainText()


def test_stubs_del_script_de_nombre():
    from app.services.script_stubs import generate_stubs

    stubs = generate_stubs("file_name")
    compile(stubs, "<stubs>", "exec")
    assert "class TransferPage" in stubs and "class LogicalDocument" in stubs
    assert "document: LogicalDocument" in stubs
    assert "documents: list[LogicalDocument]" in generate_stubs(
        "event", "on_transfer_validate"
    )
