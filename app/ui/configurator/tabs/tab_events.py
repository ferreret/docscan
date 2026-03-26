"""Pestaña Eventos — entry points de ciclo de vida.

Cada evento tiene un nombre, un entry point y un editor de código.
Se almacenan en ``Application.events_json``.
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.services.external_editor_service import detect_editor, edit_script

log = logging.getLogger(__name__)

# Entry points de ciclo de vida definidos en CLAUDE.md
EVENT_NAMES = [
    "on_app_start",
    "on_app_end",
    "on_import",
    "on_scan_complete",
    "on_transfer_validate",
    "on_transfer_advanced",
    "on_transfer_page",
    "on_navigate_prev",
    "on_navigate_next",
    "on_navigate_script",
    "on_key_event",
    "init_global",
    "verification_panel",
]

_EVENT_DESCRIPTIONS_SRC = {
    "on_app_start": QT_TRANSLATE_NOOP("EventsTab", "Al abrir la aplicación"),
    "on_app_end": QT_TRANSLATE_NOOP("EventsTab", "Al cerrar la aplicación"),
    "on_import": QT_TRANSLATE_NOOP("EventsTab", "Al pulsar Procesar (reemplaza carga estándar si está definido)"),
    "on_scan_complete": QT_TRANSLATE_NOOP("EventsTab", "Al terminar carga + todo el pipeline"),
    "on_transfer_validate": QT_TRANSLATE_NOOP("EventsTab", "Antes de transferir; retornar False cancela"),
    "on_transfer_advanced": QT_TRANSLATE_NOOP("EventsTab", "Transferencia avanzada scripteada"),
    "on_transfer_page": QT_TRANSLATE_NOOP("EventsTab", "Post-copia por página"),
    "on_navigate_prev": QT_TRANSLATE_NOOP("EventsTab", "Navegación previa programable"),
    "on_navigate_next": QT_TRANSLATE_NOOP("EventsTab", "Navegación siguiente programable"),
    "on_navigate_script": QT_TRANSLATE_NOOP("EventsTab", "Botón de navegación programable del visor"),
    "on_key_event": QT_TRANSLATE_NOOP("EventsTab", "Tecla personalizada"),
    "init_global": QT_TRANSLATE_NOOP("EventsTab", "Al iniciar el programa (script global del launcher)"),
    "verification_panel": QT_TRANSLATE_NOOP("EventsTab", "Panel de verificación (clase VerificationPanel)"),
}

_tr_evt = lambda s: QCoreApplication.translate("EventsTab", s)


def EVENT_DESCRIPTIONS() -> dict[str, str]:
    """Devuelve descripciones de eventos traducidas."""
    return {k: _tr_evt(v) for k, v in _EVENT_DESCRIPTIONS_SRC.items()}


class _EditorWorker(QThread):
    """Hilo para edición bloqueante en VS Code."""

    finished = Signal(object)  # str | None

    def __init__(self, code: str, event_name: str) -> None:
        super().__init__()
        self._code = code
        self._event_name = event_name

    def run(self) -> None:
        result = edit_script(self._code, "event", self._event_name)
        self.finished.emit(result)


class EventsTab(QWidget):
    """Editor de entry points de ciclo de vida."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: dict[str, str] = {}
        self._current_event: str = ""
        self._editor_worker: _EditorWorker | None = None
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Selector de evento
        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr("Evento:")))
        self._event_combo = QComboBox()
        self._event_combo.setToolTip(self.tr("Seleccionar el evento del ciclo de vida a editar"))
        for name in EVENT_NAMES:
            desc = EVENT_DESCRIPTIONS().get(name, "")
            self._event_combo.addItem(f"{name} — {desc}", name)
        top.addWidget(self._event_combo, 1)
        layout.addLayout(top)

        # Barra con botón VS Code
        code_bar = QHBoxLayout()
        code_bar.addStretch()
        self._btn_vscode = QPushButton(self.tr("Abrir en VS Code"))
        self._btn_vscode.setToolTip(self.tr("Editar el código en VS Code con autocompletado y sintaxis"))
        self._btn_vscode.setVisible(detect_editor() is not None)
        self._btn_vscode.clicked.connect(self._open_in_vscode)
        code_bar.addWidget(self._btn_vscode)
        layout.addLayout(code_bar)

        # Editor de código
        self._code_edit = QPlainTextEdit()
        self._code_edit.setToolTip(self.tr("Código Python para este evento. Variables: app, batch, page, log, http"))
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._code_edit.setFont(font)
        self._code_edit.setTabStopDistance(
            self._code_edit.fontMetrics().horizontalAdvance(" ") * 4
        )
        self._code_edit.setPlaceholderText(
            "def on_app_start(app, batch):\n    pass"
        )
        layout.addWidget(self._code_edit)

        # Conexiones
        self._event_combo.currentIndexChanged.connect(self._on_event_changed)

    def _load_from_app(self, app: Application) -> None:
        try:
            self._events = json.loads(app.events_json) if app.events_json else {}
        except Exception:
            self._events = {}

        self._refresh_combo_labels()

        if EVENT_NAMES:
            self._current_event = EVENT_NAMES[0]
            self._code_edit.setPlainText(
                self._events.get(self._current_event, "")
            )

    def _on_event_changed(self, index: int) -> None:
        # Guardar el código del evento anterior
        if self._current_event:
            code = self._code_edit.toPlainText()
            if code.strip():
                self._events[self._current_event] = code
            else:
                self._events.pop(self._current_event, None)
            self._refresh_combo_labels()

        # Cargar el nuevo
        self._current_event = self._event_combo.currentData()
        self._code_edit.setPlainText(
            self._events.get(self._current_event, "")
        )

    def _refresh_combo_labels(self) -> None:
        """Actualiza las etiquetas del combo marcando los eventos con código."""
        self._event_combo.blockSignals(True)
        for i in range(self._event_combo.count()):
            name = self._event_combo.itemData(i)
            desc = EVENT_DESCRIPTIONS().get(name, "")
            has_code = bool(self._events.get(name, "").strip())
            marker = "[*] " if has_code else ""
            self._event_combo.setItemText(i, f"{marker}{name} — {desc}")
        self._event_combo.blockSignals(False)

    def _open_in_vscode(self) -> None:
        """Lanza VS Code para editar el evento actual."""
        self._btn_vscode.setEnabled(False)
        self._btn_vscode.setText(self.tr("Editando en VS Code..."))
        self._editor_worker = _EditorWorker(
            self._code_edit.toPlainText(),
            self._current_event,
        )
        self._editor_worker.finished.connect(self._on_editor_done)
        self._editor_worker.start()

    def _on_editor_done(self, result: str | None) -> None:
        """Actualiza el código al volver de VS Code."""
        self._btn_vscode.setEnabled(True)
        self._btn_vscode.setText(self.tr("Abrir en VS Code"))
        if result is not None:
            self._code_edit.setPlainText(result)

    def apply_to(self, app: Application) -> None:
        """Guarda los eventos en el JSON de la aplicación."""
        # Guardar el evento actual antes de serializar
        if self._current_event:
            code = self._code_edit.toPlainText()
            if code.strip():
                self._events[self._current_event] = code
            else:
                self._events.pop(self._current_event, None)

        app.events_json = json.dumps(self._events)
