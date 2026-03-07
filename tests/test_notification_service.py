"""Tests del servicio de notificaciones."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.notification_service import (
    EmailConfig,
    NotificationResult,
    NotificationService,
    WebhookConfig,
)


@pytest.fixture
def service() -> NotificationService:
    return NotificationService()


# ------------------------------------------------------------------
# Webhook
# ------------------------------------------------------------------


class TestWebhook:
    def test_empty_url(self, service: NotificationService):
        config = WebhookConfig(url="")
        result = service.send_webhook(config, {"test": 1})
        assert not result.success
        assert "vacía" in result.detail

    @patch("app.services.notification_service.httpx.Client")
    def test_post_success(self, mock_client_cls, service: NotificationService):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = WebhookConfig(url="https://example.com/hook")
        result = service.send_webhook(config, {"batch_id": 1})
        assert result.success
        assert "200" in result.detail
        mock_client.post.assert_called_once()

    @patch("app.services.notification_service.httpx.Client")
    def test_get_method(self, mock_client_cls, service: NotificationService):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = WebhookConfig(url="https://example.com/hook", method="GET")
        result = service.send_webhook(config, {"batch_id": 1})
        assert result.success
        mock_client.get.assert_called_once()

    @patch("app.services.notification_service.httpx.Client")
    def test_connection_error(self, mock_client_cls, service: NotificationService):
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = WebhookConfig(url="https://example.com/hook")
        result = service.send_webhook(config, {})
        assert not result.success
        assert "Connection refused" in result.detail


# ------------------------------------------------------------------
# Email
# ------------------------------------------------------------------


class TestEmail:
    def test_no_host(self, service: NotificationService):
        config = EmailConfig(smtp_host="")
        result = service.send_email(config, "Test", "Body")
        assert not result.success
        assert "SMTP" in result.detail

    def test_no_recipients(self, service: NotificationService):
        config = EmailConfig(smtp_host="mail.example.com", to_addrs=[])
        result = service.send_email(config, "Test", "Body")
        assert not result.success
        assert "destinatarios" in result.detail

    @patch("app.services.notification_service.smtplib.SMTP")
    def test_send_success(self, mock_smtp_cls, service: NotificationService):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        config = EmailConfig(
            smtp_host="mail.example.com",
            smtp_port=587,
            use_tls=True,
            username="user@example.com",
            password="secret",
            to_addrs=["dest@example.com"],
        )
        result = service.send_email(config, "Asunto", "Cuerpo del mensaje")
        assert result.success
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.services.notification_service.smtplib.SMTP")
    def test_send_html(self, mock_smtp_cls, service: NotificationService):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        config = EmailConfig(
            smtp_host="mail.example.com",
            to_addrs=["dest@example.com"],
        )
        result = service.send_email(
            config, "Asunto", "<h1>HTML</h1>", html=True,
        )
        assert result.success

    @patch("app.services.notification_service.smtplib.SMTP")
    def test_smtp_error(self, mock_smtp_cls, service: NotificationService):
        mock_smtp_cls.side_effect = Exception("SMTP connection failed")

        config = EmailConfig(
            smtp_host="mail.example.com",
            to_addrs=["dest@example.com"],
        )
        result = service.send_email(config, "Test", "Body")
        assert not result.success
        assert "SMTP connection failed" in result.detail


# ------------------------------------------------------------------
# Notificaciones de alto nivel
# ------------------------------------------------------------------


class TestHighLevel:
    @patch("app.services.notification_service.httpx.Client")
    def test_notify_transfer_complete(
        self, mock_client_cls, service: NotificationService,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        webhook = WebhookConfig(url="https://example.com/hook")
        results = service.notify_transfer_complete(
            webhook=webhook, email=None,
            batch_id=1, app_name="Test",
            stats={"total_pages": 10},
        )
        assert len(results) == 1
        assert results[0].success

    def test_notify_no_channels(self, service: NotificationService):
        results = service.notify_transfer_complete(
            webhook=None, email=None,
            batch_id=1, app_name="Test", stats={},
        )
        assert results == []

    @patch("app.services.notification_service.httpx.Client")
    def test_notify_error(
        self, mock_client_cls, service: NotificationService,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        webhook = WebhookConfig(url="https://example.com/hook")
        results = service.notify_error(
            webhook=webhook, email=None,
            batch_id=1, app_name="Test", error="Pipeline failed",
        )
        assert len(results) == 1
        assert results[0].success
