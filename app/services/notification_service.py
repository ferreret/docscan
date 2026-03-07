"""Servicio de notificaciones — webhooks y email.

Envía notificaciones al completar transferencias, detectar errores,
o cualquier evento configurable por aplicación.
"""

from __future__ import annotations

import json
import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Configuración de un webhook."""

    url: str = ""
    method: str = "POST"  # "POST" o "GET"
    headers: dict[str, str] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class EmailConfig:
    """Configuración SMTP para envío de emails."""

    smtp_host: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)


@dataclass
class NotificationResult:
    """Resultado de un envío de notificación."""

    success: bool = True
    channel: str = ""  # "webhook" o "email"
    detail: str = ""


class NotificationService:
    """Servicio de notificaciones por webhook y email."""

    def send_webhook(
        self,
        config: WebhookConfig,
        payload: dict[str, Any],
    ) -> NotificationResult:
        """Envía una notificación por webhook.

        Args:
            config: Configuración del webhook.
            payload: Datos a enviar como JSON.

        Returns:
            Resultado del envío.
        """
        if not config.url:
            return NotificationResult(
                success=False, channel="webhook",
                detail="URL de webhook vacía",
            )

        try:
            headers = {"Content-Type": "application/json", **config.headers}

            with httpx.Client(timeout=config.timeout) as client:
                if config.method.upper() == "GET":
                    resp = client.get(
                        config.url, params=payload, headers=headers,
                    )
                else:
                    resp = client.post(
                        config.url, json=payload, headers=headers,
                    )

            resp.raise_for_status()
            log.info("Webhook enviado a %s: %d", config.url, resp.status_code)
            return NotificationResult(
                success=True, channel="webhook",
                detail=f"HTTP {resp.status_code}",
            )

        except httpx.HTTPStatusError as e:
            msg = f"Webhook error HTTP {e.response.status_code}: {config.url}"
            log.error(msg)
            return NotificationResult(
                success=False, channel="webhook", detail=msg,
            )
        except Exception as e:
            msg = f"Webhook error: {e}"
            log.error(msg)
            return NotificationResult(
                success=False, channel="webhook", detail=msg,
            )

    def send_email(
        self,
        config: EmailConfig,
        subject: str,
        body: str,
        html: bool = False,
    ) -> NotificationResult:
        """Envía una notificación por email.

        Args:
            config: Configuración SMTP.
            subject: Asunto del email.
            body: Cuerpo del mensaje.
            html: Si el body es HTML.

        Returns:
            Resultado del envío.
        """
        if not config.smtp_host:
            return NotificationResult(
                success=False, channel="email",
                detail="Host SMTP no configurado",
            )

        if not config.to_addrs:
            return NotificationResult(
                success=False, channel="email",
                detail="Sin destinatarios",
            )

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = config.from_addr or config.username
            msg["To"] = ", ".join(config.to_addrs)

            if html:
                msg.set_content(body, subtype="html")
            else:
                msg.set_content(body)

            if config.use_tls:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)

            try:
                if config.username:
                    server.login(config.username, config.password)
                server.send_message(msg)
            finally:
                server.quit()

            log.info("Email enviado a %s", config.to_addrs)
            return NotificationResult(
                success=True, channel="email",
                detail=f"Enviado a {len(config.to_addrs)} destinatario(s)",
            )

        except Exception as e:
            msg_err = f"Error enviando email: {e}"
            log.error(msg_err)
            return NotificationResult(
                success=False, channel="email", detail=msg_err,
            )

    def notify_transfer_complete(
        self,
        webhook: WebhookConfig | None,
        email: EmailConfig | None,
        batch_id: int,
        app_name: str,
        stats: dict[str, Any],
    ) -> list[NotificationResult]:
        """Notifica que una transferencia se ha completado.

        Envía por todos los canales configurados.
        """
        results: list[NotificationResult] = []

        payload = {
            "event": "transfer_complete",
            "batch_id": batch_id,
            "application": app_name,
            "stats": stats,
        }

        if webhook and webhook.url:
            results.append(self.send_webhook(webhook, payload))

        if email and email.smtp_host and email.to_addrs:
            subject = f"[DocScan] Transferencia completada — {app_name}"
            body = (
                f"Lote {batch_id} transferido.\n"
                f"Aplicación: {app_name}\n"
                f"Páginas: {stats.get('total_pages', '?')}\n"
                f"Revisión: {stats.get('needs_review', 0)}\n"
            )
            results.append(self.send_email(email, subject, body))

        return results

    def notify_error(
        self,
        webhook: WebhookConfig | None,
        email: EmailConfig | None,
        batch_id: int,
        app_name: str,
        error: str,
    ) -> list[NotificationResult]:
        """Notifica un error en el procesado."""
        results: list[NotificationResult] = []

        payload = {
            "event": "processing_error",
            "batch_id": batch_id,
            "application": app_name,
            "error": error,
        }

        if webhook and webhook.url:
            results.append(self.send_webhook(webhook, payload))

        if email and email.smtp_host and email.to_addrs:
            subject = f"[DocScan] Error — {app_name}"
            body = (
                f"Error en lote {batch_id}.\n"
                f"Aplicación: {app_name}\n"
                f"Error: {error}\n"
            )
            results.append(self.send_email(email, subject, body))

        return results
