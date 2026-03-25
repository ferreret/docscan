"""Dialogo del asistente IA para generacion de codigo de eventos.

Permite al usuario describir en lenguaje natural el comportamiento
deseado de un evento lifecycle y genera el codigo Python.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QCoreApplication,
    QT_TRANSLATE_NOOP,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.pipeline_assistant import AssistantResponse
from app.workers.pipeline_assistant_worker import PipelineAssistantWorker
from config.secrets import SecretsManager

log = logging.getLogger(__name__)

_ctx = "EventAssistantDialog"

_TITLE = QT_TRANSLATE_NOOP(_ctx, "Asistente IA — {event}")
_LABEL_SEND = QT_TRANSLATE_NOOP(_ctx, "Enviar")
_LABEL_ACCEPT = QT_TRANSLATE_NOOP(_ctx, "Aplicar codigo")
_LABEL_CLOSE = QT_TRANSLATE_NOOP(_ctx, "Cerrar")
_LABEL_PLACEHOLDER = QT_TRANSLATE_NOOP(
    _ctx, "Describe lo que debe hacer el evento..."
)
_LABEL_API_KEY = QT_TRANSLATE_NOOP(_ctx, "API Key:")
_LABEL_SAVE_KEY = QT_TRANSLATE_NOOP(_ctx, "Guardar")
_LABEL_WAITING = QT_TRANSLATE_NOOP(_ctx, "Generando codigo...")
_LABEL_NO_KEY = QT_TRANSLATE_NOOP(
    _ctx, "Configura tu API key para usar el asistente."
)
_LABEL_KEY_SAVED = QT_TRANSLATE_NOOP(_ctx, "API key guardada.")
_PROVIDERS = QT_TRANSLATE_NOOP(_ctx, "Anthropic|OpenAI")

_tr = lambda s: QCoreApplication.translate(_ctx, s)

_PROVIDER_MAP = {"Anthropic": "anthropic", "OpenAI": "openai"}
_SECRET_KEYS = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}


class _ChatInput(QPlainTextEdit):
    """QPlainTextEdit que envia con Ctrl+Enter."""

    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class EventAssistantDialog(QDialog):
    """Dialogo modal con chat para generar codigo de eventos lifecycle.

    Signals:
        code_generated: Emitida con el codigo Python generado.
    """

    code_generated = Signal(str)

    def __init__(
        self,
        event_name: str,
        event_description: str,
        current_code: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._event_name = event_name
        self._event_description = event_description
        self._current_code = current_code
        self._generated_code: str | None = None
        self._messages: list[dict[str, str]] = []
        self._secrets = SecretsManager()
        self._worker = PipelineAssistantWorker(self)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(
            _tr(_TITLE).format(event=self._event_name)
        )
        self.setMinimumSize(600, 500)
        self.resize(700, 550)

        layout = QVBoxLayout(self)

        # Info del evento
        info = QLabel(
            f"<b>{self._event_name}</b> — {self._event_description}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Proveedor
        prov_layout = QHBoxLayout()
        self._combo_provider = QComboBox()
        for label in _tr(_PROVIDERS).split("|"):
            self._combo_provider.addItem(label.strip())
        self._combo_provider.currentIndexChanged.connect(
            lambda _: self._check_api_key()
        )
        prov_layout.addWidget(self._combo_provider)
        prov_layout.addStretch()
        layout.addLayout(prov_layout)

        # Area de mensajes
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._messages_layout.setContentsMargins(2, 2, 2, 2)
        self._messages_layout.setSpacing(6)
        self._scroll.setWidget(self._messages_container)
        layout.addWidget(self._scroll, 1)

        # Status
        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        layout.addWidget(self._lbl_status)

        # API key inline
        self._key_frame = QFrame()
        key_layout = QHBoxLayout(self._key_frame)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(QLabel(_tr(_LABEL_API_KEY)))
        self._input_key = QLineEdit()
        self._input_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._input_key.setPlaceholderText("sk-...")
        key_layout.addWidget(self._input_key, 1)
        self._btn_save_key = QPushButton(_tr(_LABEL_SAVE_KEY))
        self._btn_save_key.clicked.connect(self._save_api_key)
        key_layout.addWidget(self._btn_save_key)
        self._key_frame.setVisible(False)
        layout.addWidget(self._key_frame)

        # Input
        input_layout = QHBoxLayout()
        self._input = _ChatInput()
        self._input.setPlaceholderText(_tr(_LABEL_PLACEHOLDER))
        self._input.setMaximumHeight(80)
        self._input.setFont(QFont("monospace", 9))
        self._input.submit_requested.connect(self._on_send)
        input_layout.addWidget(self._input, 1)

        self._btn_send = QPushButton(_tr(_LABEL_SEND))
        self._btn_send.clicked.connect(self._on_send)
        input_layout.addWidget(self._btn_send, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_layout)

        # Botones de dialogo
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._btn_accept = QPushButton(_tr(_LABEL_ACCEPT))
        self._btn_accept.setEnabled(False)
        self._btn_accept.clicked.connect(self._on_accept)
        self._btn_close = QPushButton(_tr(_LABEL_CLOSE))
        self._btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_accept)
        btn_layout.addWidget(self._btn_close)
        layout.addLayout(btn_layout)

        self._check_api_key()

    # ------------------------------------------------------------------
    # API key
    # ------------------------------------------------------------------

    def _get_provider_id(self) -> str:
        label = self._combo_provider.currentText()
        return _PROVIDER_MAP.get(label, "anthropic")

    def _get_secret_key(self) -> str:
        return _SECRET_KEYS[self._get_provider_id()]

    def _check_api_key(self) -> None:
        has_key = self._secrets.has(self._get_secret_key())
        self._key_frame.setVisible(not has_key)
        if not has_key:
            self._lbl_status.setText(_tr(_LABEL_NO_KEY))
        else:
            self._lbl_status.clear()

    def _save_api_key(self) -> None:
        key = self._input_key.text().strip()
        if not key:
            return
        self._secrets.set(self._get_secret_key(), key)
        self._input_key.clear()
        self._key_frame.setVisible(False)
        self._lbl_status.setText(_tr(_LABEL_KEY_SAVED))

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return

        api_key = self._secrets.get(self._get_secret_key())
        if not api_key:
            self._key_frame.setVisible(True)
            self._lbl_status.setText(_tr(_LABEL_NO_KEY))
            return

        self._add_message("user", text)
        self._input.clear()
        self._messages.append({"role": "user", "content": text})

        self._worker.configure(
            provider=self._get_provider_id(),
            api_key=api_key,
        )
        self._btn_send.setEnabled(False)
        self._lbl_status.setText(_tr(_LABEL_WAITING))

        self._worker.send_event_message(
            messages=list(self._messages),
            event_name=self._event_name,
            current_code=self._current_code,
        )

    def _on_response(self, response: AssistantResponse) -> None:
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()

        if response.error:
            self._add_message("error", response.error)
            return

        if response.text:
            self._add_message("assistant", response.text)
            self._messages.append({"role": "assistant", "content": response.text})

        if response.explanation:
            self._add_message("assistant", response.explanation)
            if not response.text:
                self._messages.append({
                    "role": "assistant",
                    "content": response.explanation,
                })

        if response.event_code:
            self._generated_code = response.event_code
            self._add_code_preview(response.event_code)
            self._btn_accept.setEnabled(True)
            # Actualizar el codigo actual para futuras peticiones
            self._current_code = response.event_code

    def _on_error(self, error_msg: str) -> None:
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()
        self._add_message("error", error_msg)

    def _on_accept(self) -> None:
        if self._generated_code:
            self.code_generated.emit(self._generated_code)
            self.accept()

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------

    def _add_message(self, role: str, text: str) -> None:
        bubble = QFrame()
        if role == "user":
            bubble.setObjectName("chatBubbleUser")
        elif role == "error":
            bubble.setObjectName("chatBubbleError")
        else:
            bubble.setObjectName("chatBubbleAssistant")

        blayout = QVBoxLayout(bubble)
        blayout.setContentsMargins(8, 6, 8, 6)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        blayout.addWidget(label)

        self._messages_layout.addWidget(bubble)
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _add_code_preview(self, code: str) -> None:
        """Muestra una preview del codigo generado."""
        frame = QFrame()
        frame.setObjectName("chatCodePreview")
        flayout = QVBoxLayout(frame)
        flayout.setContentsMargins(4, 4, 4, 4)

        code_edit = QPlainTextEdit()
        code_edit.setReadOnly(True)
        code_edit.setPlainText(code)
        code_edit.setFont(QFont("monospace", 9))
        code_edit.setMaximumHeight(200)
        flayout.addWidget(code_edit)

        self._messages_layout.addWidget(frame)
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )
