"""Tests del configurador de aplicación."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
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
            pipeline_json=serialize([
                ImageOpStep(id="s1", op="AutoDeskew"),
                BarcodeStep(id="s2", engine="motor2", symbologies=["QR"]),
            ]),
            events_json=json.dumps({
                "on_app_start": "def on_app_start(app, batch):\n    pass",
            }),
            transfer_json=json.dumps({
                "mode": "pdf",
                "destination": "/tmp/output",
                "pdf_dpi": 300,
            }),
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

    def test_disabled_marker(self):
        step = ImageOpStep(id="s1", op="Crop", enabled=False)
        text = _step_display_text(step)
        assert "[✗]" in text


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
        dialog._code_edit.setPlainText("def my_func(app, batch, page, pipeline):\n    pass")
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
        sample_app.batch_fields_json = json.dumps([
            {"label": "Expediente", "type": "texto", "required": True},
            {"label": "Prioridad", "type": "lista", "required": False,
             "config": {"values": ["Alta", "Media", "Baja"]}},
            {"label": "Páginas", "type": "numérico", "required": False,
             "config": {"min": 1, "max": 500, "step": 1}},
        ])
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
        sample_app.batch_fields_json = json.dumps([
            {"label": "Campo1", "type": "texto", "required": False},
        ])
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
        sample_app.batch_fields_json = json.dumps([
            {"label": "Nombre", "type": "texto", "required": True},
            {"label": "Estado", "type": "lista", "required": False,
             "config": {"values": ["Abierto", "Cerrado"]}},
            {"label": "Cantidad", "type": "numérico", "required": True,
             "config": {"min": 0, "max": 999, "step": 5}},
        ])
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
        sample_app.batch_fields_json = json.dumps([
            {"label": "A", "type": "texto", "required": False},
            {"label": "B", "type": "texto", "required": False},
            {"label": "C", "type": "texto", "required": False},
        ])
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
        sample_app.batch_fields_json = json.dumps([
            {"label": "Primero", "type": "texto", "required": False},
            {"label": "Segundo", "type": "lista", "required": True,
             "config": {"values": ["X", "Y"]}},
        ])
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(0, 1)  # Mover "Primero" abajo

        label_0 = self._get_label(tab, 0).text()
        label_1 = self._get_label(tab, 1).text()
        assert label_0 == "Segundo"
        assert label_1 == "Primero"

    def test_move_row_up(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps([
            {"label": "A", "type": "texto", "required": False},
            {"label": "B", "type": "numérico", "required": True,
             "config": {"min": 0, "max": 10, "step": 1}},
        ])
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(1, -1)  # Mover "B" arriba

        label_0 = self._get_label(tab, 0).text()
        label_1 = self._get_label(tab, 1).text()
        assert label_0 == "B"
        assert label_1 == "A"

    def test_move_row_boundary_no_crash(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps([
            {"label": "Solo", "type": "texto", "required": False},
        ])
        tab = BatchFieldsTab(sample_app)
        qtbot.addWidget(tab)

        tab._move_row(0, -1)  # No puede subir más
        tab._move_row(0, 1)   # No puede bajar más
        assert tab._table.rowCount() == 1

    def test_required_checkbox_state(self, qtbot, sample_app):
        sample_app.batch_fields_json = json.dumps([
            {"label": "Req", "type": "texto", "required": True},
            {"label": "Opt", "type": "texto", "required": False},
        ])
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
        assert dialog._tabs.count() == 6
        assert dialog.windowTitle().startswith("Configurar")
