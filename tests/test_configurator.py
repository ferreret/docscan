"""Tests del configurador de aplicación."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox, QLineEdit
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
        tab._code_edit.setPlainText("def on_app_start(app, batch):\n    print('hi')")
        tab.apply_to(sample_app)
        events = json.loads(sample_app.events_json)
        assert "on_app_start" in events

    def test_empty_event_removed(self, qtbot, sample_app):
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        tab._code_edit.setPlainText("")
        tab.apply_to(sample_app)
        events = json.loads(sample_app.events_json)
        assert "on_app_start" not in events

    def test_event_names_includes_on_batch_loaded_and_on_page_changed(self):
        """v0.1.1: ambos eventos deben aparecer en el catálogo."""
        from app.ui.configurator.tabs.tab_events import EVENT_NAMES, EVENT_DESCRIPTIONS

        assert "on_batch_loaded" in EVENT_NAMES
        assert "on_page_changed" in EVENT_NAMES
        descriptions = EVENT_DESCRIPTIONS()
        assert descriptions.get("on_batch_loaded")
        assert descriptions.get("on_page_changed")

    def test_placeholder_changes_with_selected_event(self, qtbot, sample_app):
        """v0.1.1: el placeholder del editor debe reflejar la firma del
        evento seleccionado. Antes estaba hardcoded a ``on_app_start``
        para todos los eventos.
        """
        tab = EventsTab(sample_app)
        qtbot.addWidget(tab)
        # Al cargar, el primer evento es on_app_start.
        assert "on_app_start" in tab._code_edit.placeholderText()
        # Cambiar a on_page_changed → placeholder debe llevar `page` en la firma.
        idx = tab._event_combo.findData("on_page_changed")
        assert idx >= 0, "on_page_changed no está en el combo"
        tab._event_combo.setCurrentIndex(idx)
        ph = tab._code_edit.placeholderText()
        assert "def on_page_changed(app, batch, page, page_index):" in ph
        # Cambiar a on_key_event → debe llevar `key` en la firma.
        idx2 = tab._event_combo.findData("on_key_event")
        tab._event_combo.setCurrentIndex(idx2)
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
        dialog._symb_edit.setText("QR, Code128")
        result = dialog.get_step()
        assert result.engine == "motor2"
        assert result.symbologies == ["QR", "Code128"]


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
    def test_empty_fields(self, qtbot, sample_app):
        sample_app.batch_fields_json = "[]"
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._table.rowCount() == 0

    @staticmethod
    def _get_label(tab, row):
        """Obtiene el QLineEdit de etiqueta de una fila."""
        return tab._table.cellWidget(row, 0).findChild(QLineEdit)

    @staticmethod
    def _get_type_combo(tab, row):
        """Obtiene el QComboBox de tipo de una fila."""
        return tab._table.cellWidget(row, 1).findChild(QComboBox)

    def test_loads_existing_fields(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
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
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._table.rowCount() == 3

        # Verificar primera fila: texto
        label_w = self._get_label(tab, 0)
        assert isinstance(label_w, QLineEdit)
        assert label_w.text() == "Expediente"
        type_w = self._get_type_combo(tab, 0)
        assert isinstance(type_w, QComboBox)
        assert type_w.currentText() == "texto"

        # Verificar segunda fila: lista
        label_w = self._get_label(tab, 1)
        assert label_w.text() == "Prioridad"
        config_w = tab._table.cellWidget(1, 2)
        values_edit = config_w.findChild(QLineEdit, "listValues")
        assert values_edit is not None
        assert "Alta" in values_edit.text()

        # Verificar tercera fila: numérico
        config_w = tab._table.cellWidget(2, 2)
        spin_min = config_w.findChild(QSpinBox, "numMin")
        assert spin_min is not None
        assert spin_min.value() == 1

    def test_add_field(self, qtbot, sample_app):
        sample_app.batch_fields_json = "[]"
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._table.rowCount() == 0

        # Simular click en "Añadir campo"
        tab._add_empty_row()
        assert tab._table.rowCount() == 1

        # La fila nueva tiene tipo "texto" por defecto
        type_w = self._get_type_combo(tab, 0)
        assert type_w.currentText() == "texto"

    def test_change_type_updates_config_widget(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "Campo1", "type": "texto", "required": False},
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        # Cambiar a numérico
        type_w = self._get_type_combo(tab, 0)
        type_w.setCurrentText("numérico")

        config_w = tab._table.cellWidget(0, 2)
        assert config_w.findChild(QSpinBox, "numMin") is not None

        # Cambiar a lista
        type_w = self._get_type_combo(tab, 0)
        type_w.setCurrentText("lista")

        config_w = tab._table.cellWidget(0, 2)
        assert config_w.findChild(QLineEdit, "listValues") is not None

    def test_apply_to_serializes_all_types(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
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
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        result_app = Application(name="Result")
        tab.apply_to(result_app)

        fields = json.loads(result_app.batch_fields_json)
        assert len(fields) == 3

        assert fields[0]["label"] == "Nombre"
        assert fields[0]["type"] == "texto"
        assert fields[0]["required"] is True

        assert fields[1]["label"] == "Estado"
        assert fields[1]["type"] == "lista"
        assert fields[1]["config"]["values"] == ["Abierto", "Cerrado"]

        assert fields[2]["label"] == "Cantidad"
        assert fields[2]["type"] == "numérico"
        assert fields[2]["config"]["min"] == 0
        assert fields[2]["config"]["max"] == 999
        assert fields[2]["config"]["step"] == 5

    def test_empty_label_rows_skipped_on_apply(self, qtbot, sample_app):
        sample_app.batch_fields_json = "[]"
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._add_empty_row()  # Label vacío
        tab._add_empty_row()
        # Poner label solo en la segunda
        label_w = self._get_label(tab, 1)
        label_w.setText("Campo Real")

        result_app = Application(name="R")
        tab.apply_to(result_app)
        fields = json.loads(result_app.batch_fields_json)
        assert len(fields) == 1
        assert fields[0]["label"] == "Campo Real"

    def test_remove_row(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "A", "type": "texto", "required": False},
                {"label": "B", "type": "texto", "required": False},
                {"label": "C", "type": "texto", "required": False},
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)
        assert tab._table.rowCount() == 3

        tab._remove_row(1)  # Eliminar "B"
        assert tab._table.rowCount() == 2

        labels = []
        for r in range(tab._table.rowCount()):
            w = self._get_label(tab, r)
            labels.append(w.text())
        assert labels == ["A", "C"]

    def test_move_row_down(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "Primero", "type": "texto", "required": False},
                {
                    "label": "Segundo",
                    "type": "lista",
                    "required": True,
                    "config": {"values": ["X", "Y"]},
                },
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(0, 1)  # Mover "Primero" abajo

        label_0 = self._get_label(tab, 0).text()
        label_1 = self._get_label(tab, 1).text()
        assert label_0 == "Segundo"
        assert label_1 == "Primero"

    def test_move_row_up(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "A", "type": "texto", "required": False},
                {
                    "label": "B",
                    "type": "numérico",
                    "required": True,
                    "config": {"min": 0, "max": 10, "step": 1},
                },
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(1, -1)  # Mover "B" arriba

        label_0 = self._get_label(tab, 0).text()
        label_1 = self._get_label(tab, 1).text()
        assert label_0 == "B"
        assert label_1 == "A"

    def test_move_row_boundary_no_crash(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "Solo", "type": "texto", "required": False},
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(0, -1)  # No puede subir más
        tab._move_row(0, 1)  # No puede bajar más
        assert tab._table.rowCount() == 1

    def test_required_checkbox_state(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps(
            [
                {"label": "Req", "type": "texto", "required": True},
                {"label": "Opt", "type": "texto", "required": False},
            ]
        )
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        req_w = tab._table.cellWidget(0, 3)
        cb0 = req_w.findChild(QCheckBox)
        assert cb0.isChecked() is True

        opt_w = tab._table.cellWidget(1, 3)
        cb1 = opt_w.findChild(QCheckBox)
        assert cb1.isChecked() is False


# ------------------------------------------------------------------
# App Configurator
# ------------------------------------------------------------------


class TestAppConfigurator:
    def test_creates_with_tabs(self, qtbot, sample_app, session_factory):
        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        assert dialog._tabs.count() == 7
        assert dialog.windowTitle().startswith("Configurar")

    def test_no_guarda_si_un_evento_no_compila(
        self, qtbot, sample_app, session_factory
    ):
        """Paridad FlexibarNET10 v1.20: el Configurador rechaza scripts rotos."""
        from unittest.mock import patch

        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        tab = dialog._tab_events
        assert tab._current_event == "on_app_start"
        tab._code_edit.setPlainText("def on_app_start(app, batch:\n")
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
        assert dialog._sep_group.isChecked()
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
        dialog._sep_group.setChecked(False)
        dialog._sep_mode.setCurrentIndex(dialog._sep_mode.findData("fixed_value"))
        out = dialog.get_step()
        assert not out.separator_enabled
        assert out.separator_by == "fixed_value"


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

    def test_un_backend_de_otra_plataforma_se_conserva(self, qtbot, sample_app):
        sample_app.scanner_backend = "twain"
        tab = GeneralTab(sample_app)
        qtbot.addWidget(tab)
        tab.apply_to(sample_app)
        assert sample_app.scanner_backend == "twain"
