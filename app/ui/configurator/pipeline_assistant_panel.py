"""Panel de chat del asistente IA para construccion de pipelines.

Panel lateral que permite al usuario describir en lenguaje natural
lo que necesita y recibe propuestas de pipeline con diff visual.
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
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.serializer import serialize
from app.pipeline.steps import PipelineStep
from app.services.pipeline_assistant import AssistantResponse
from app.ui.configurator.pipeline_diff_widget import PipelineDiffWidget
from app.workers.pipeline_assistant_worker import PipelineAssistantWorker
from config.secrets import SecretsManager

log = logging.getLogger(__name__)

_ctx = "PipelineAssistantPanel"

_PROVIDERS = QT_TRANSLATE_NOOP(_ctx, "Anthropic|OpenAI")
_LABEL_SEND = QT_TRANSLATE_NOOP(_ctx, "Enviar")
_LABEL_NEW_CHAT = QT_TRANSLATE_NOOP(_ctx, "Nueva conversacion")
_LABEL_PLACEHOLDER = QT_TRANSLATE_NOOP(
    _ctx, "Describe el pipeline que necesitas..."
)
_LABEL_API_KEY = QT_TRANSLATE_NOOP(_ctx, "API Key:")
_LABEL_SAVE_KEY = QT_TRANSLATE_NOOP(_ctx, "Guardar")
_LABEL_WAITING = QT_TRANSLATE_NOOP(_ctx, "Generando respuesta...")
_LABEL_NO_KEY = QT_TRANSLATE_NOOP(
    _ctx, "Configura tu API key para usar el asistente."
)
_LABEL_KEY_SAVED = QT_TRANSLATE_NOOP(_ctx, "API key guardada.")

_tr = lambda s: QCoreApplication.translate(_ctx, s)

# Mapa de proveedor UI -> clave interna
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


class PipelineAssistantPanel(QWidget):
    """Panel lateral de chat para el asistente IA de pipelines.

    Signals:
        pipeline_proposed: Emitida con la lista de pasos propuestos.
        pipeline_accepted: Emitida cuando el usuario acepta una propuesta.
    """

    pipeline_proposed = Signal(list)
    pipeline_accepted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pipelineAssistantPanel")
        self._messages: list[dict[str, str]] = []
        self._current_steps: list[PipelineStep] = []
        self._proposed_steps: list[PipelineStep] | None = None
        self._secrets = SecretsManager()
        self._worker = PipelineAssistantWorker(self)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Cabecera: proveedor + nueva conversacion
        header = QHBoxLayout()
        self._combo_provider = QComboBox()
        for label in _tr(_PROVIDERS).split("|"):
            self._combo_provider.addItem(label.strip())
        self._combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        header.addWidget(self._combo_provider)

        self._btn_new = QPushButton(_tr(_LABEL_NEW_CHAT))
        self._btn_new.setObjectName("assistantNewChatBtn")
        self._btn_new.clicked.connect(self._clear_chat)
        header.addWidget(self._btn_new)
        layout.addLayout(header)

        # Area de mensajes scrollable
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

        # Status label
        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("assistantStatus")
        self._lbl_status.setWordWrap(True)
        layout.addWidget(self._lbl_status)

        # API key inline (oculto por defecto)
        self._key_frame = QFrame()
        self._key_frame.setObjectName("assistantKeyFrame")
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

        # Input + enviar
        input_layout = QHBoxLayout()
        self._input = _ChatInput()
        self._input.setObjectName("assistantInput")
        self._input.setPlaceholderText(_tr(_LABEL_PLACEHOLDER))
        self._input.setMaximumHeight(80)
        font = QFont("monospace", 9)
        self._input.setFont(font)
        self._input.submit_requested.connect(self._on_send)
        input_layout.addWidget(self._input, 1)

        self._btn_send = QPushButton(_tr(_LABEL_SEND))
        self._btn_send.setObjectName("assistantSendBtn")
        self._btn_send.clicked.connect(self._on_send)
        input_layout.addWidget(self._btn_send, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_layout)

        # Comprobar API key inicial
        self._check_api_key()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def set_current_pipeline(self, steps: list[PipelineStep]) -> None:
        """Actualiza el pipeline actual como contexto para el asistente."""
        self._current_steps = list(steps)

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_provider_changed(self, _index: int) -> None:
        self._check_api_key()

    def _get_provider_id(self) -> str:
        label = self._combo_provider.currentText()
        return _PROVIDER_MAP.get(label, "anthropic")

    def _get_secret_key(self) -> str:
        return _SECRET_KEYS[self._get_provider_id()]

    def _check_api_key(self) -> None:
        """Comprueba si hay API key y muestra/oculta el input."""
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

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return

        # Verificar API key
        secret_key = self._get_secret_key()
        api_key = self._secrets.get(secret_key)
        if not api_key:
            self._key_frame.setVisible(True)
            self._lbl_status.setText(_tr(_LABEL_NO_KEY))
            return

        # Mostrar mensaje del usuario
        self._add_message("user", text)
        self._input.clear()

        # Agregar al historial
        self._messages.append({"role": "user", "content": text})

        # Configurar y enviar
        self._worker.configure(
            provider=self._get_provider_id(),
            api_key=api_key,
        )
        self._btn_send.setEnabled(False)
        self._lbl_status.setText(_tr(_LABEL_WAITING))

        pipeline_json = serialize(self._current_steps)
        self._worker.send_pipeline_message(
            messages=list(self._messages),
            pipeline_json=pipeline_json,
        )

    def _on_response(self, response: AssistantResponse) -> None:
        """Procesa la respuesta del asistente."""
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()

        if response.error:
            self._add_message("error", response.error)
            return

        # Texto libre del asistente
        if response.text:
            self._add_message("assistant", response.text)
            self._messages.append({"role": "assistant", "content": response.text})

        # Explicacion
        if response.explanation:
            self._add_message("assistant", response.explanation)
            if not response.text:
                self._messages.append({
                    "role": "assistant",
                    "content": response.explanation,
                })

        # Propuesta de pipeline con diff
        if response.steps is not None:
            self._proposed_steps = response.steps
            self._show_diff(self._current_steps, response.steps)
            self.pipeline_proposed.emit(response.steps)

    def _on_error(self, error_msg: str) -> None:
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()
        self._add_message("error", error_msg)

    def _clear_chat(self) -> None:
        """Limpia la conversacion."""
        self._messages.clear()
        self._proposed_steps = None
        # Limpiar widgets del area de mensajes
        while self._messages_layout.count():
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._lbl_status.clear()

    # ------------------------------------------------------------------
    # Mensajes y diff
    # ------------------------------------------------------------------

    def _add_message(self, role: str, text: str) -> None:
        """Agrega una burbuja de mensaje al area de chat."""
        bubble = QFrame()
        bubble.setProperty("chatRole", role)
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
        # Auto-scroll al final
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _show_diff(
        self,
        current: list[PipelineStep],
        proposed: list[PipelineStep],
    ) -> None:
        """Muestra el widget de diff inline."""
        diff_widget = PipelineDiffWidget(current, proposed)
        diff_widget.accepted.connect(lambda: self._on_diff_accepted(diff_widget))
        diff_widget.rejected.connect(lambda: self._on_diff_rejected(diff_widget))
        self._messages_layout.addWidget(diff_widget)
        # Auto-scroll
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _on_diff_accepted(self, widget: PipelineDiffWidget) -> None:
        widget.setEnabled(False)
        self.pipeline_accepted.emit()
        self._add_message("assistant", "Pipeline aplicado.")

    def _on_diff_rejected(self, widget: PipelineDiffWidget) -> None:
        widget.setEnabled(False)
        self._proposed_steps = None
        self._add_message("assistant", "Propuesta descartada.")
