"""Tests para NotificationConfig — configuración de notificaciones (webhook)."""

from __future__ import annotations

import json

from app.services.notification_service import (
    NotificationConfig,
    WebhookConfig,
    parse_notification_config,
    serialize_notification_config,
)


class TestNotificationConfigDefaults:
    def test_default_values(self):
        config = NotificationConfig()
        assert config.webhook_enabled is False
        assert config.webhook == WebhookConfig()
        assert config.webhook.url == ""
        assert config.webhook.method == "POST"
        assert config.webhook.headers == {}
        assert config.webhook.timeout == 30


class TestParseNotificationConfig:
    def test_parse_empty_string(self):
        assert parse_notification_config("") == NotificationConfig()

    def test_parse_empty_json(self):
        assert parse_notification_config("{}") == NotificationConfig()

    def test_parse_valid_json(self):
        data = json.dumps(
            {
                "webhook_enabled": True,
                "webhook": {
                    "url": "https://ejemplo.com/hook",
                    "method": "GET",
                    "headers": {"Authorization": "Bearer x"},
                    "timeout": 10,
                },
            }
        )
        config = parse_notification_config(data)
        assert config.webhook_enabled is True
        assert config.webhook.url == "https://ejemplo.com/hook"
        assert config.webhook.method == "GET"
        assert config.webhook.headers == {"Authorization": "Bearer x"}
        assert config.webhook.timeout == 10

    def test_parse_partial_webhook_keeps_defaults(self):
        data = json.dumps({"webhook_enabled": True, "webhook": {"url": "https://x/h"}})
        config = parse_notification_config(data)
        assert config.webhook.url == "https://x/h"
        assert config.webhook.method == "POST"  # default
        assert config.webhook.timeout == 30  # default

    def test_parse_ignores_unknown_webhook_fields(self):
        data = json.dumps(
            {"webhook": {"url": "https://x/h", "desconocido": "valor", "otro": 42}}
        )
        config = parse_notification_config(data)
        assert config.webhook.url == "https://x/h"
        assert not hasattr(config.webhook, "desconocido")

    def test_parse_missing_webhook_key(self):
        """Sin clave 'webhook', se usa el WebhookConfig por defecto."""
        config = parse_notification_config(json.dumps({"webhook_enabled": True}))
        assert config.webhook_enabled is True
        assert config.webhook == WebhookConfig()

    def test_parse_enabled_coerced_to_bool(self):
        config = parse_notification_config(json.dumps({"webhook_enabled": 1}))
        assert config.webhook_enabled is True


class TestSerializeNotificationConfig:
    def test_serialize_defaults(self):
        result = serialize_notification_config(NotificationConfig())
        data = json.loads(result)
        assert data["webhook_enabled"] is False
        assert data["webhook"]["method"] == "POST"

    def test_roundtrip(self):
        original = NotificationConfig(
            webhook_enabled=True,
            webhook=WebhookConfig(
                url="https://ejemplo/hook",
                method="GET",
                headers={"X-Origen": "DocScan"},
                timeout=15,
            ),
        )
        restored = parse_notification_config(serialize_notification_config(original))
        assert restored == original

    def test_roundtrip_defaults(self):
        original = NotificationConfig()
        restored = parse_notification_config(serialize_notification_config(original))
        assert restored == original
