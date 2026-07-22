"""Pestaña Notificaciones del configurador."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.services.notification_service import (
    WebhookConfig,
    parse_notification_config,
    serialize_notification_config,
)


class NotificationsTab(QWidget):
    """Configuración de notificaciones (webhook) de la aplicación.

    Al completar (o fallar) la transferencia de un lote, el worker envía una
    notificación HTTP a la URL configurada aquí. El envío de email SMTP se
    reserva para una iteración posterior.
    """

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ── Grupo: Webhook ──
        webhook_group = QGroupBox(self.tr("Webhook"))
        form = QFormLayout(webhook_group)
        form.setVerticalSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(
            self.tr(
                "Envía una notificación HTTP al completar o fallar la\n"
                "transferencia de un lote. El cuerpo incluye el evento, el\n"
                "identificador del lote, la aplicación y las estadísticas."
            )
        )
        intro.setObjectName("hint_label")
        intro.setWordWrap(True)
        form.addRow(intro)

        self._enabled_check = QCheckBox(self.tr("Habilitar webhook"))
        self._enabled_check.setToolTip(
            self.tr(
                "Si está desmarcado, no se envía ninguna notificación HTTP\n"
                "aunque haya una URL configurada."
            )
        )
        self._enabled_check.toggled.connect(self._on_enabled_changed)
        form.addRow("", self._enabled_check)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://ejemplo.com/webhook")
        self._url_edit.setToolTip(
            self.tr("URL de destino de la notificación (http o https)")
        )
        form.addRow(self.tr("URL:"), self._url_edit)

        self._method_combo = QComboBox()
        self._method_combo.addItem("POST", "POST")
        self._method_combo.addItem("GET", "GET")
        self._method_combo.setToolTip(
            self.tr(
                "POST = envía el cuerpo como JSON\n"
                "GET = envía los datos como parámetros de consulta"
            )
        )
        form.addRow(self.tr("Método:"), self._method_combo)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(1, 300)
        self._timeout_spin.setValue(30)
        self._timeout_spin.setSuffix(self.tr(" s"))
        self._timeout_spin.setToolTip(
            self.tr("Tiempo máximo de espera de la respuesta HTTP")
        )
        form.addRow(self.tr("Timeout:"), self._timeout_spin)

        self._headers_edit = QPlainTextEdit()
        self._headers_edit.setPlaceholderText(
            "Authorization: Bearer XXXX\nX-Origen: DocScan"
        )
        self._headers_edit.setToolTip(
            self.tr(
                "Cabeceras HTTP adicionales, una por línea, en formato\n"
                "«Nombre: valor». Útil para tokens de autenticación."
            )
        )
        self._headers_edit.setFixedHeight(90)
        form.addRow(self.tr("Cabeceras:"), self._headers_edit)

        headers_hint = QLabel(
            self.tr("Una cabecera por línea, con el formato «Nombre: valor».")
        )
        headers_hint.setObjectName("hint_label")
        headers_hint.setWordWrap(True)
        form.addRow(headers_hint)

        main_layout.addWidget(webhook_group)
        main_layout.addStretch()

    def _on_enabled_changed(self, enabled: bool) -> None:
        """Habilita/deshabilita los controles del webhook."""
        self._url_edit.setEnabled(enabled)
        self._method_combo.setEnabled(enabled)
        self._timeout_spin.setEnabled(enabled)
        self._headers_edit.setEnabled(enabled)

    @staticmethod
    def _headers_to_text(headers: dict[str, str]) -> str:
        """Convierte un dict de cabeceras al texto «Nombre: valor» por línea."""
        return "\n".join(f"{key}: {value}" for key, value in headers.items())

    @staticmethod
    def _text_to_headers(text: str) -> dict[str, str]:
        """Parsea el texto «Nombre: valor» por línea a un dict de cabeceras."""
        headers: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, value = line.split(":", 1)
            name = name.strip()
            if name:
                headers[name] = value.strip()
        return headers

    def _load_from_app(self, app: Application) -> None:
        config = parse_notification_config(app.notifications_json)
        webhook = config.webhook

        self._enabled_check.setChecked(config.webhook_enabled)
        self._url_edit.setText(webhook.url)
        idx = self._method_combo.findData(webhook.method)
        if idx >= 0:
            self._method_combo.setCurrentIndex(idx)
        self._timeout_spin.setValue(webhook.timeout)
        self._headers_edit.setPlainText(self._headers_to_text(webhook.headers))

        self._on_enabled_changed(config.webhook_enabled)

    def apply_to(self, app: Application) -> None:
        from app.services.notification_service import NotificationConfig

        webhook = WebhookConfig(
            url=self._url_edit.text().strip(),
            method=self._method_combo.currentData(),
            headers=self._text_to_headers(self._headers_edit.toPlainText()),
            timeout=self._timeout_spin.value(),
        )
        config = NotificationConfig(
            webhook_enabled=self._enabled_check.isChecked(),
            webhook=webhook,
        )
        app.notifications_json = serialize_notification_config(config)
