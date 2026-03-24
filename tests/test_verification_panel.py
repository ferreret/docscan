"""Tests del panel de verificación personalizado."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.workbench.verification_panel import VerificationPanel, WorkbenchAPI


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_api(**overrides) -> WorkbenchAPI:
    """Crea un WorkbenchAPI con mocks por defecto."""
    defaults = {
        "session_factory": MagicMock(),
        "get_pages": lambda: [],
        "get_batch_id": lambda: 1,
        "get_current_index": lambda: 0,
        "navigate_fn": MagicMock(),
        "log_fn": MagicMock(),
        "get_batch_fields_fn": lambda: {},
        "set_batch_field_fn": MagicMock(),
    }
    defaults.update(overrides)
    return WorkbenchAPI(**defaults)


# ------------------------------------------------------------------
# VerificationPanel base
# ------------------------------------------------------------------


class TestVerificationPanelBase:
    """Tests de la clase base VerificationPanel."""

    def test_default_validate_returns_true(self, qapp):
        api = _make_api()
        panel = VerificationPanel(api)
        ok, msg = panel.validate()
        assert ok is True
        assert msg == ""

    def test_default_validate_page_returns_true(self, qapp):
        api = _make_api()
        panel = VerificationPanel(api)
        ok, msg = panel.validate_page(0)
        assert ok is True
        assert msg == ""

    def test_default_hooks_are_noop(self, qapp):
        api = _make_api()
        panel = VerificationPanel(api)
        panel.on_page_changed(0)
        panel.on_pipeline_completed(0)
        panel.on_batch_loaded()
        panel.cleanup()

    def test_api_accessible(self, qapp):
        api = _make_api()
        panel = VerificationPanel(api)
        assert panel.api is api


# ------------------------------------------------------------------
# Subclase de usuario
# ------------------------------------------------------------------


class TestCustomPanel:
    """Tests de subclases personalizadas de VerificationPanel."""

    def test_custom_setup_ui(self, qapp):
        class MyPanel(VerificationPanel):
            def setup_ui(self):
                layout = QVBoxLayout(self)
                self.label = QLabel("Test")
                layout.addWidget(self.label)

        api = _make_api()
        panel = MyPanel(api)
        assert panel.label.text() == "Test"

    def test_custom_validate_false(self, qapp):
        class StrictPanel(VerificationPanel):
            def validate(self):
                return False, "Campo obligatorio vacío"

        api = _make_api()
        panel = StrictPanel(api)
        ok, msg = panel.validate()
        assert ok is False
        assert "obligatorio" in msg

    def test_custom_validate_page(self, qapp):
        page0 = MagicMock()
        page0.index_fields_json = '{"nif": "B12345"}'
        page1 = MagicMock()
        page1.index_fields_json = '{}'

        class PageValidator(VerificationPanel):
            def validate_page(self, page_index):
                fields = self.api.get_page_fields(page_index)
                if not fields.get("nif"):
                    return False, f"Página {page_index + 1}: NIF obligatorio"
                return True, ""

        api = _make_api(get_pages=lambda: [page0, page1])
        panel = PageValidator(api)
        ok, msg = panel.validate_page(0)
        assert ok is True
        ok, msg = panel.validate_page(1)
        assert ok is False
        assert "Página 2" in msg

    def test_on_page_changed_receives_index(self, qapp):
        received = []

        class TrackingPanel(VerificationPanel):
            def on_page_changed(self, page_index):
                received.append(page_index)

        api = _make_api()
        panel = TrackingPanel(api)
        panel.on_page_changed(5)
        panel.on_page_changed(10)
        assert received == [5, 10]

    def test_on_pipeline_completed_receives_index(self, qapp):
        received = []

        class TrackingPanel(VerificationPanel):
            def on_pipeline_completed(self, page_index):
                received.append(page_index)

        api = _make_api()
        panel = TrackingPanel(api)
        panel.on_pipeline_completed(3)
        assert received == [3]


# ------------------------------------------------------------------
# WorkbenchAPI
# ------------------------------------------------------------------


class TestWorkbenchAPI:
    """Tests de la fachada WorkbenchAPI."""

    def test_current_page(self):
        api = _make_api(get_current_index=lambda: 7)
        assert api.current_page == 7

    def test_page_count(self):
        pages = [MagicMock(), MagicMock(), MagicMock()]
        api = _make_api(get_pages=lambda: pages)
        assert api.get_page_count() == 3

    def test_navigate_to(self):
        nav = MagicMock()
        api = _make_api(navigate_fn=nav)
        api.navigate_to(5)
        nav.assert_called_once_with(5)

    def test_log(self):
        log_fn = MagicMock()
        api = _make_api(log_fn=log_fn)
        api.log("hola")
        log_fn.assert_called_once_with("hola")

    def test_get_batch_fields(self):
        api = _make_api(get_batch_fields_fn=lambda: {"fecha": "2026-03-24"})
        assert api.get_batch_fields() == {"fecha": "2026-03-24"}

    def test_set_batch_field(self):
        setter = MagicMock()
        api = _make_api(set_batch_field_fn=setter)
        api.set_batch_field("fecha", "2026-03-25")
        setter.assert_called_once_with("fecha", "2026-03-25")

    def test_get_page_image_out_of_range(self):
        api = _make_api(get_pages=lambda: [])
        assert api.get_page_image(0) is None

    def test_get_page_barcodes_out_of_range(self):
        api = _make_api(get_pages=lambda: [])
        assert api.get_page_barcodes(0) == []

    def test_get_page_ocr_text_out_of_range(self):
        api = _make_api(get_pages=lambda: [])
        assert api.get_page_ocr_text(0) == ""

    def test_get_page_fields_out_of_range(self):
        api = _make_api(get_pages=lambda: [])
        assert api.get_page_fields(0) == {}

    def test_get_page_fields_valid(self):
        page = MagicMock()
        page.index_fields_json = '{"nif": "B12345"}'
        api = _make_api(get_pages=lambda: [page])
        assert api.get_page_fields(0) == {"nif": "B12345"}

    def test_get_page_ocr_text_valid(self):
        page = MagicMock()
        page.ocr_text = "Hello World"
        api = _make_api(get_pages=lambda: [page])
        assert api.get_page_ocr_text(0) == "Hello World"


# ------------------------------------------------------------------
# Descubrimiento de clases
# ------------------------------------------------------------------


class TestClassDiscovery:
    """Tests para la lógica de descubrimiento de subclases."""

    def test_finds_subclass_in_namespace(self, qapp):
        source = """
class MiPanel(VerificationPanel):
    def setup_ui(self):
        pass
"""
        code = compile(source, "<test>", "exec")
        namespace = {
            "__builtins__": __builtins__,
            "VerificationPanel": VerificationPanel,
        }
        exec(code, namespace)

        panel_class = None
        for obj in namespace.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, VerificationPanel)
                and obj is not VerificationPanel
            ):
                panel_class = obj
                break

        assert panel_class is not None
        assert panel_class.__name__ == "MiPanel"

    def test_no_subclass_returns_none(self, qapp):
        source = "x = 42"
        code = compile(source, "<test>", "exec")
        namespace = {
            "__builtins__": __builtins__,
            "VerificationPanel": VerificationPanel,
        }
        exec(code, namespace)

        panel_class = None
        for obj in namespace.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, VerificationPanel)
                and obj is not VerificationPanel
            ):
                panel_class = obj
                break

        assert panel_class is None

    def test_syntax_error_caught(self):
        source = "class Broken(:"
        with pytest.raises(SyntaxError):
            compile(source, "<test>", "exec")
