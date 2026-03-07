"""Pestaña Eventos — entry points de ciclo de vida.

Cada evento tiene un nombre, un entry point y un editor de código.
Se almacenan en ``Application.events_json``.
"""

from __future__ import annotations

import json

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application

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
    "on_key_event",
    "init_global",
]

EVENT_DESCRIPTIONS = {
    "on_app_start": "Al abrir la aplicación",
    "on_app_end": "Al cerrar la aplicación",
    "on_import": "Al pulsar Procesar (reemplaza carga estándar si está definido)",
    "on_scan_complete": "Al terminar carga + todo el pipeline",
    "on_transfer_validate": "Antes de transferir; retornar False cancela",
    "on_transfer_advanced": "Transferencia avanzada scripteada",
    "on_transfer_page": "Post-copia por página",
    "on_navigate_prev": "Navegación previa programable",
    "on_navigate_next": "Navegación siguiente programable",
    "on_key_event": "Tecla personalizada",
    "init_global": "Al iniciar el programa (script global del launcher)",
}


class EventsTab(QWidget):
    """Editor de entry points de ciclo de vida."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: dict[str, str] = {}
        self._current_event: str = ""
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Selector de evento
        top = QHBoxLayout()
        top.addWidget(QLabel("Evento:"))
        self._event_combo = QComboBox()
        for name in EVENT_NAMES:
            desc = EVENT_DESCRIPTIONS.get(name, "")
            self._event_combo.addItem(f"{name} — {desc}", name)
        top.addWidget(self._event_combo, 1)
        layout.addLayout(top)

        # Editor de código
        self._code_edit = QPlainTextEdit()
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

        # Cargar el nuevo
        self._current_event = self._event_combo.currentData()
        self._code_edit.setPlainText(
            self._events.get(self._current_event, "")
        )

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
