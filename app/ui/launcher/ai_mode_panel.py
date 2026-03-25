"""Panel AI MODE — asistente IA unificado en el Launcher.

Panel lateral de chat que puede crear, modificar, duplicar y
eliminar aplicaciones completas de DocScan Studio.
"""

from __future__ import annotations

import json
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
    QVBoxLayout,
    QWidget,
)

from app.db.repositories.application_repo import ApplicationRepository
from app.models.application import Application
from app.services.ai_mode_assistant import (
    AiModeResponse,
    AiModeToolCall,
    validate_pipeline,
)
from app.ui.launcher.app_change_preview import AppChangePreview
from app.workers.ai_mode_worker import AiModeWorker
from config.secrets import SecretsManager

log = logging.getLogger(__name__)

_ctx = "AiModePanel"

_PROVIDERS = QT_TRANSLATE_NOOP(_ctx, "Anthropic|OpenAI")
_LABEL_SEND = QT_TRANSLATE_NOOP(_ctx, "Enviar")
_LABEL_NEW_CHAT = QT_TRANSLATE_NOOP(_ctx, "Nueva conversacion")
_LABEL_PLACEHOLDER = QT_TRANSLATE_NOOP(
    _ctx, "Describe lo que necesitas (crear app, modificar pipeline, etc.)..."
)
_LABEL_API_KEY = QT_TRANSLATE_NOOP(_ctx, "API Key:")
_LABEL_SAVE_KEY = QT_TRANSLATE_NOOP(_ctx, "Guardar")
_LABEL_WAITING = QT_TRANSLATE_NOOP(_ctx, "Generando respuesta...")
_LABEL_NO_KEY = QT_TRANSLATE_NOOP(
    _ctx, "Configura tu API key para usar el asistente."
)
_LABEL_KEY_SAVED = QT_TRANSLATE_NOOP(_ctx, "API key guardada.")

_tr = lambda s: QCoreApplication.translate(_ctx, s)

_PROVIDER_MAP = {"Anthropic": "anthropic", "OpenAI": "openai"}
_SECRET_KEYS = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}


class _ChatInput(QPlainTextEdit):
    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class AiModePanel(QWidget):
    """Panel lateral de chat AI MODE.

    Signals:
        apps_changed: Emitida cuando se crea/modifica/elimina una app.
    """

    apps_changed = Signal()

    def __init__(
        self,
        session_factory: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("aiModePanel")
        self._session_factory = session_factory
        self._messages: list[dict[str, str]] = []
        self._secrets = SecretsManager()
        self._worker = AiModeWorker(self)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._last_provider = ""
        self._last_api_key = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Titulo
        title = QLabel("<b>AI MODE</b>")
        title.setObjectName("aiModeTitle")
        layout.addWidget(title)

        # Proveedor + nueva conversacion
        header = QHBoxLayout()
        self._combo_provider = QComboBox()
        for label in _tr(_PROVIDERS).split("|"):
            self._combo_provider.addItem(label.strip())
        self._combo_provider.currentIndexChanged.connect(
            lambda _: self._check_api_key()
        )
        header.addWidget(self._combo_provider)

        self._btn_new = QPushButton(_tr(_LABEL_NEW_CHAT))
        self._btn_new.setObjectName("assistantNewChatBtn")
        self._btn_new.clicked.connect(self._clear_chat)
        header.addWidget(self._btn_new)
        layout.addLayout(header)

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
        self._lbl_status.setObjectName("assistantStatus")
        self._lbl_status.setWordWrap(True)
        layout.addWidget(self._lbl_status)

        # API key inline
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
        self._input.setFont(QFont("monospace", 9))
        self._input.submit_requested.connect(self._on_send)
        input_layout.addWidget(self._input, 1)

        self._btn_send = QPushButton(_tr(_LABEL_SEND))
        self._btn_send.setObjectName("assistantSendBtn")
        self._btn_send.clicked.connect(self._on_send)
        input_layout.addWidget(self._btn_send, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_layout)

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
    # Apps summary
    # ------------------------------------------------------------------

    def _build_apps_summary(self) -> str:
        """Genera JSON con resumen de todas las apps."""
        try:
            with self._session_factory() as session:
                repo = ApplicationRepository(session)
                apps = repo.get_all()
                summary = []
                for app in apps:
                    try:
                        raw = json.loads(app.pipeline_json) if app.pipeline_json else []
                        step_count = len(raw)
                        step_types = [s.get("type", "?") for s in raw]
                    except Exception:
                        step_count = 0
                        step_types = []

                    # Eventos con codigo
                    try:
                        events = json.loads(app.events_json) if app.events_json else {}
                        event_names = [k for k, v in events.items() if v.strip()]
                    except Exception:
                        event_names = []

                    # Campos de lote
                    try:
                        fields = json.loads(app.batch_fields_json) if app.batch_fields_json else []
                        field_labels = [f.get("label", "?") for f in fields]
                    except Exception:
                        field_labels = []

                    summary.append({
                        "name": app.name,
                        "description": app.description or "",
                        "active": app.active,
                        "pipeline_steps": step_count,
                        "pipeline_types": step_types,
                        "events_with_code": event_names,
                        "batch_fields": field_labels,
                        "output_format": app.output_format,
                        "auto_transfer": app.auto_transfer,
                    })

                return json.dumps(summary, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("Error al construir apps_summary: %s", e)
            return "[]"

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

        provider = self._get_provider_id()
        if provider != self._last_provider or api_key != self._last_api_key:
            self._worker.configure(provider=provider, api_key=api_key)
            self._last_provider = provider
            self._last_api_key = api_key
        self._btn_send.setEnabled(False)
        self._lbl_status.setText(_tr(_LABEL_WAITING))

        apps_summary = self._build_apps_summary()
        self._worker.send_message(
            messages=list(self._messages),
            apps_summary=apps_summary,
        )

    def _on_response(self, response: AiModeResponse) -> None:
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()

        if response.error:
            self._add_message("error", response.error)
            return

        assistant_parts: list[str] = []

        if response.text:
            self._add_message("assistant", response.text)
            assistant_parts.append(response.text)

        for tc in response.tool_calls:
            if tc.tool_name in ("list_applications", "get_application"):
                self._handle_info_tool(tc)
            else:
                self._show_change_preview(tc)
            assistant_parts.append(self._summarize_tool_call(tc))

        # Un solo mensaje assistant en historial para evitar fragmentacion multi-tool
        if assistant_parts:
            full_response = "\n".join(assistant_parts)
            self._messages.append({"role": "assistant", "content": full_response})

    def _summarize_tool_call(self, tc: AiModeToolCall) -> str:
        """Genera un resumen textual de un tool call para el historial."""
        ti = tc.tool_input
        if tc.tool_name == "create_application":
            n_steps = len(ti.get("pipeline", []))
            events = list(ti.get("events", {}).keys())
            return (
                f"[Executed tool: create_application] "
                f"Created app '{ti.get('name', '?')}' with {n_steps} pipeline steps"
                f"{f', events: {events}' if events else ''}. "
                f"{tc.explanation}"
            )
        elif tc.tool_name == "update_application":
            changed = [k for k in ("pipeline", "events", "batch_fields", "general")
                       if k in ti]
            return (
                f"[Executed tool: update_application] "
                f"Updated '{ti.get('app_name', '?')}' — changed: {changed}. "
                f"{tc.explanation}"
            )
        elif tc.tool_name == "duplicate_application":
            return (
                f"[Executed tool: duplicate_application] "
                f"Duplicated '{ti.get('source_app_name', '?')}' as "
                f"'{ti.get('new_name', '?')}'. {tc.explanation}"
            )
        elif tc.tool_name == "delete_application":
            return (
                f"[Executed tool: delete_application] "
                f"Deleted '{ti.get('app_name', '?')}'. {tc.explanation}"
            )
        elif tc.tool_name == "set_event_code":
            return (
                f"[Executed tool: set_event_code] "
                f"Set event '{ti.get('event_name', '?')}' on "
                f"'{ti.get('app_name', '?')}'. {tc.explanation}"
            )
        elif tc.tool_name == "list_applications":
            return "[Executed tool: list_applications]"
        elif tc.tool_name == "get_application":
            return f"[Executed tool: get_application] Fetched '{ti.get('app_name', '?')}'"
        return f"[Executed tool: {tc.tool_name}]"

    def _on_error(self, error_msg: str) -> None:
        self._btn_send.setEnabled(True)
        self._lbl_status.clear()
        self._add_message("error", error_msg)

    def _clear_chat(self) -> None:
        self._messages.clear()
        while self._messages_layout.count():
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._lbl_status.clear()

    # ------------------------------------------------------------------
    # Info tools (no requieren confirmacion)
    # ------------------------------------------------------------------

    def _handle_info_tool(self, tc: AiModeToolCall) -> None:
        """Maneja tools informativos (sin preview). El historial se gestiona en _on_response."""
        if tc.tool_name == "list_applications":
            summary = self._build_apps_summary()
            self._add_message("assistant", f"Aplicaciones actuales:\n{summary}")
        elif tc.tool_name == "get_application":
            app_name = tc.tool_input.get("app_name", "?")
            config = self._get_full_app_config(app_name)
            if config:
                text = f"Configuracion de {app_name}:\n{json.dumps(config, ensure_ascii=False, indent=2)}"
                self._add_message("assistant", text)
            else:
                self._add_message("error", f"Aplicacion '{app_name}' no encontrada.")

    def _get_full_app_config(self, app_name: str) -> dict | None:
        try:
            with self._session_factory() as session:
                repo = ApplicationRepository(session)
                app = repo.get_by_name(app_name)
                if not app:
                    return None
                return {
                    "name": app.name,
                    "description": app.description,
                    "active": app.active,
                    "pipeline_json": app.pipeline_json,
                    "events_json": app.events_json,
                    "transfer_json": app.transfer_json,
                    "batch_fields_json": app.batch_fields_json,
                    "index_fields_json": app.index_fields_json,
                    "image_config_json": app.image_config_json,
                    "ai_config_json": app.ai_config_json,
                    "auto_transfer": app.auto_transfer,
                    "close_after_transfer": app.close_after_transfer,
                    "output_format": app.output_format,
                    "scanner_backend": app.scanner_backend,
                }
        except Exception as e:
            log.error("Error al obtener config de %s: %s", app_name, e)
            return None

    # ------------------------------------------------------------------
    # Change preview
    # ------------------------------------------------------------------

    def _show_change_preview(self, tc: AiModeToolCall) -> None:
        if tc.explanation:
            self._add_message("assistant", tc.explanation)

        preview = AppChangePreview(
            tool_name=tc.tool_name,
            tool_input=tc.tool_input,
            explanation=tc.explanation,
        )
        preview.accepted.connect(
            lambda ti, tn=tc.tool_name: self._execute_tool(tn, ti)
        )
        preview.rejected.connect(lambda p=preview: self._on_preview_rejected(p))
        self._messages_layout.addWidget(preview)
        self._scroll_to_bottom()

    def _on_preview_rejected(self, preview: AppChangePreview) -> None:
        preview.set_enabled_state(False)
        self._add_message("assistant", "Propuesta descartada.")
        self._messages.append({
            "role": "user",
            "content": "[User rejected the proposed change]",
        })

    # ------------------------------------------------------------------
    # Ejecucion BD
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, tool_input: dict) -> None:
        """Ejecuta la operacion BD correspondiente al tool."""
        try:
            if tool_name == "create_application":
                self._exec_create(tool_input)
            elif tool_name == "update_application":
                self._exec_update(tool_input)
            elif tool_name == "duplicate_application":
                self._exec_duplicate(tool_input)
            elif tool_name == "delete_application":
                self._exec_delete(tool_input)
            elif tool_name == "set_event_code":
                self._exec_set_event(tool_input)
            else:
                self._add_message("error", f"Operacion desconocida: {tool_name}")
                return
            # Registrar aceptacion en historial
            self._messages.append({
                "role": "user",
                "content": f"[User accepted and executed: {tool_name}]",
            })
        except Exception as e:
            log.error("Error ejecutando %s: %s", tool_name, e)
            self._add_message("error", f"Error: {e}")

    def _exec_create(self, ti: dict) -> None:
        name = ti["name"]
        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            if repo.get_by_name(name):
                self._add_message("error", f"Ya existe una aplicacion '{name}'.")
                return

            app = Application(name=name)
            app.description = ti.get("description", "")
            app.active = ti.get("active", True)

            self._apply_config_to_app(app, ti)

            repo.save(app)
            session.commit()

        self._add_message("assistant", f"Aplicacion '{name}' creada.")
        self.apps_changed.emit()

    def _exec_update(self, ti: dict) -> None:
        app_name = ti["app_name"]
        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_name(app_name)
            if not app:
                self._add_message("error", f"Aplicacion '{app_name}' no encontrada.")
                return

            # Actualizar nombre si se proporciona y es diferente
            if "name" in ti and ti["name"] != app_name:
                if repo.get_by_name(ti["name"]):
                    self._add_message("error", f"Ya existe una aplicacion '{ti['name']}'.")
                    return
                app.name = ti["name"]

            if "description" in ti:
                app.description = ti["description"]
            if "active" in ti:
                app.active = ti["active"]

            self._apply_config_to_app(app, ti)
            session.commit()

        self._add_message("assistant", f"Aplicacion '{app_name}' actualizada.")
        self.apps_changed.emit()

    def _exec_duplicate(self, ti: dict) -> None:
        source_name = ti["source_app_name"]
        new_name = ti["new_name"]

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            source = repo.get_by_name(source_name)
            if not source:
                self._add_message("error", f"Aplicacion '{source_name}' no encontrada.")
                return
            if repo.get_by_name(new_name):
                self._add_message("error", f"Ya existe una aplicacion '{new_name}'.")
                return

            clone = Application(
                name=new_name,
                description=ti.get("description", source.description),
                active=ti.get("active", source.active),
                pipeline_json=source.pipeline_json,
                events_json=source.events_json,
                transfer_json=source.transfer_json,
                batch_fields_json=source.batch_fields_json,
                index_fields_json=source.index_fields_json,
                auto_transfer=source.auto_transfer,
                close_after_transfer=source.close_after_transfer,
                background_color=source.background_color,
                output_format=source.output_format,
                default_tab=source.default_tab,
                scanner_backend=source.scanner_backend,
                image_config_json=source.image_config_json,
                ai_config_json=source.ai_config_json,
            )

            # Aplicar modificaciones
            self._apply_config_to_app(clone, ti)

            repo.save(clone)
            session.commit()

        self._add_message(
            "assistant",
            f"Aplicacion '{source_name}' duplicada como '{new_name}'.",
        )
        self.apps_changed.emit()

    def _exec_delete(self, ti: dict) -> None:
        app_name = ti["app_name"]
        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_name(app_name)
            if not app:
                self._add_message("error", f"Aplicacion '{app_name}' no encontrada.")
                return
            repo.delete(app.id)
            session.commit()

        self._add_message("assistant", f"Aplicacion '{app_name}' eliminada.")
        self.apps_changed.emit()

    def _exec_set_event(self, ti: dict) -> None:
        app_name = ti["app_name"]
        event_name = ti["event_name"]
        code = ti["code"]

        with self._session_factory() as session:
            repo = ApplicationRepository(session)
            app = repo.get_by_name(app_name)
            if not app:
                self._add_message("error", f"Aplicacion '{app_name}' no encontrada.")
                return

            try:
                events = json.loads(app.events_json) if app.events_json else {}
            except Exception:
                events = {}

            events[event_name] = code
            app.events_json = json.dumps(events, ensure_ascii=False)
            session.commit()

        self._add_message(
            "assistant",
            f"Evento '{event_name}' actualizado en '{app_name}'.",
        )
        self.apps_changed.emit()

    # ------------------------------------------------------------------
    # Aplicar config comun (pipeline, events, fields, etc.)
    # ------------------------------------------------------------------

    def _apply_config_to_app(self, app: Application, ti: dict) -> None:
        """Aplica campos opcionales de un tool_input a una Application."""
        if "pipeline" in ti:
            pipeline_data = ti["pipeline"]
            error = validate_pipeline(pipeline_data)
            if error:
                log.warning("Pipeline invalido, se guarda como JSON raw: %s", error)
            app.pipeline_json = json.dumps(pipeline_data, ensure_ascii=False)

        if "events" in ti:
            app.events_json = json.dumps(ti["events"], ensure_ascii=False)

        if "batch_fields" in ti:
            app.batch_fields_json = json.dumps(ti["batch_fields"], ensure_ascii=False)

        if "index_fields" in ti:
            app.index_fields_json = json.dumps(ti["index_fields"], ensure_ascii=False)

        if "transfer" in ti:
            app.transfer_json = json.dumps(ti["transfer"], ensure_ascii=False)

        if "image_config" in ti:
            app.image_config_json = json.dumps(ti["image_config"], ensure_ascii=False)

        if "ai_config" in ti:
            app.ai_config_json = json.dumps(ti["ai_config"], ensure_ascii=False)

        general = ti.get("general", {})
        if "auto_transfer" in general:
            app.auto_transfer = general["auto_transfer"]
        if "close_after_transfer" in general:
            app.close_after_transfer = general["close_after_transfer"]
        if "output_format" in general:
            app.output_format = general["output_format"]
        if "default_tab" in general:
            app.default_tab = general["default_tab"]
        if "scanner_backend" in general:
            app.scanner_backend = general["scanner_backend"]
        if "background_color" in general:
            app.background_color = general["background_color"]

    # ------------------------------------------------------------------
    # Mensajes UI
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
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
