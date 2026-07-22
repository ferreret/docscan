"""Tests de la pestaña Notificaciones del configurador."""

from __future__ import annotations

import json

from app.models.application import Application
from app.models.batch import Batch  # noqa: F401  # registra el mapper ORM
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.services.notification_service import parse_notification_config
from app.ui.configurator.tabs.tab_notifications import NotificationsTab


def _app(notifications_json: str = "{}") -> Application:
    """Application transitoria (sin BD) con la config de notificaciones dada."""
    return Application(name="Test", notifications_json=notifications_json)


class TestNotificationsTab:
    def test_loads_defaults(self, qtbot):
        tab = NotificationsTab(_app())
        qtbot.addWidget(tab)
        assert tab._enabled_check.isChecked() is False
        assert tab._url_edit.text() == ""
        assert tab._method_combo.currentData() == "POST"
        assert tab._timeout_spin.value() == 30
        # Controles deshabilitados cuando el webhook está apagado
        assert tab._url_edit.isEnabled() is False

    def test_loads_configured_values(self, qtbot):
        cfg = json.dumps(
            {
                "webhook_enabled": True,
                "webhook": {
                    "url": "https://x/hook",
                    "method": "GET",
                    "headers": {"Authorization": "Bearer t"},
                    "timeout": 12,
                },
            }
        )
        tab = NotificationsTab(_app(cfg))
        qtbot.addWidget(tab)
        assert tab._enabled_check.isChecked() is True
        assert tab._url_edit.text() == "https://x/hook"
        assert tab._method_combo.currentData() == "GET"
        assert tab._timeout_spin.value() == 12
        assert "Authorization: Bearer t" in tab._headers_edit.toPlainText()
        assert tab._url_edit.isEnabled() is True

    def test_apply_to_roundtrip(self, qtbot):
        app = _app()
        tab = NotificationsTab(app)
        qtbot.addWidget(tab)
        tab._enabled_check.setChecked(True)
        tab._url_edit.setText("https://y/hook")
        tab._method_combo.setCurrentIndex(tab._method_combo.findData("GET"))
        tab._timeout_spin.setValue(45)
        tab._headers_edit.setPlainText("X-Token: abc\nX-Origen: DocScan")
        tab.apply_to(app)

        cfg = parse_notification_config(app.notifications_json)
        assert cfg.webhook_enabled is True
        assert cfg.webhook.url == "https://y/hook"
        assert cfg.webhook.method == "GET"
        assert cfg.webhook.timeout == 45
        assert cfg.webhook.headers == {"X-Token": "abc", "X-Origen": "DocScan"}

    def test_headers_parsing_ignores_malformed_lines(self, qtbot):
        app = _app()
        tab = NotificationsTab(app)
        qtbot.addWidget(tab)
        tab._enabled_check.setChecked(True)
        tab._url_edit.setText("https://z/hook")
        tab._headers_edit.setPlainText("linea-sin-dospuntos\n\nBuena: valor\n")
        tab.apply_to(app)

        cfg = parse_notification_config(app.notifications_json)
        assert cfg.webhook.headers == {"Buena": "valor"}
