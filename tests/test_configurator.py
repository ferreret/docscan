"""Tests del configurador de aplicación."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.pipeline.steps import (
    ImageOpStep,
    BarcodeStep,
    OcrStep,
    AiStep,
    ScriptStep,
    ConditionStep,
    HttpRequestStep,
)
from app.pipeline.serializer import serialize
from app.ui.configurator.app_configurator import AppConfigurator
from app.ui.configurator.tabs.tab_general import GeneralTab
from app.ui.configurator.tabs.tab_pipeline import PipelineTab, _step_display_text
from app.ui.configurator.tabs.tab_events import EventsTab
from app.ui.configurator.tabs.tab_transfer import TransferTab
from app.ui.configurator.step_dialogs.image_op_dialog import ImageOpDialog
from app.ui.configurator.step_dialogs.barcode_step_dialog import BarcodeStepDialog
from app.ui.configurator.step_dialogs.ocr_step_dialog import OcrStepDialog
from app.ui.configurator.step_dialogs.ai_step_dialog import AiStepDialog
from app.ui.configurator.step_dialogs.script_step_dialog import ScriptStepDialog
from app.ui.configurator.step_dialogs.condition_step_dialog import ConditionStepDialog
from app.ui.configurator.step_dialogs.http_request_dialog import HttpRequestDialog


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
        tab._format_combo.setCurrentText("png")
        tab.apply_to(sample_app)
        assert sample_app.name == "Renamed App"
        assert sample_app.output_format == "png"


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


class TestAiStepDialog:
    def test_get_step(self, qtbot):
        step = AiStep(id="s1")
        dialog = AiStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._provider_combo.setCurrentText("openai")
        dialog._template_spin.setValue(5)
        result = dialog.get_step()
        assert result.provider == "openai"
        assert result.template_id == 5

    def test_no_template(self, qtbot):
        step = AiStep(id="s1")
        dialog = AiStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._template_spin.setValue(0)
        result = dialog.get_step()
        assert result.template_id is None


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


class TestConditionStepDialog:
    def test_get_step(self, qtbot):
        step = ConditionStep(id="s1")
        dialog = ConditionStepDialog(step)
        qtbot.addWidget(dialog)
        dialog._expr_edit.setText("len(page.barcodes) > 0")
        dialog._on_false_edit.setText("skip_to:step_005")
        result = dialog.get_step()
        assert result.expression == "len(page.barcodes) > 0"
        assert result.on_false == "skip_to:step_005"


class TestHttpRequestDialog:
    def test_get_step(self, qtbot):
        step = HttpRequestStep(id="s1")
        dialog = HttpRequestDialog(step)
        qtbot.addWidget(dialog)
        dialog._method_combo.setCurrentText("POST")
        dialog._url_edit.setText("https://api.example.com")
        dialog._headers_edit.setText("Authorization: Bearer xxx")
        dialog._on_error_combo.setCurrentText("abort")
        result = dialog.get_step()
        assert result.method == "POST"
        assert result.url == "https://api.example.com"
        assert result.headers == {"Authorization": "Bearer xxx"}
        assert result.on_error == "abort"


# ------------------------------------------------------------------
# AppConfigurator (integración)
# ------------------------------------------------------------------


class TestAppConfigurator:
    def test_creates_with_tabs(self, qtbot, sample_app, session_factory):
        dialog = AppConfigurator(sample_app, session_factory)
        qtbot.addWidget(dialog)
        assert dialog._tabs.count() == 4
        assert dialog.windowTitle().startswith("Configurar")
