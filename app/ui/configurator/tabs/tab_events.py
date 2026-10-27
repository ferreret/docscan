"""Pestaña Eventos — entry points de ciclo de vida.

Presentación de FlexibarNET10: lista de eventos a la izquierda, con punto de
estado (vacío, ACTIVO o PAUSADO), nombre legible y nombre canónico; a la
derecha, el detalle del evento seleccionado con la casilla «Activado», el
resumen del código y el botón «Editar script…», que abre el editor con el
panel de variables disponibles.

Se almacenan en ``Application.events_json`` con las formas que describe
``app.services.event_config``: texto si el evento está activado y
``{"script", "enabled": false}`` si está pausado.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QSize, QT_TRANSLATE_NOOP, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.services._assistant_constants import EVENT_SIGNATURES
from app.services.event_config import (
    event_enabled,
    event_source,
    make_event_entry,
    parse_events,
)
from app.ui.configurator.event_script_dialog import EventScriptDialog
from app.ui.widgets.code_editor import CodeEditor

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
    "on_batch_loaded",
    "on_page_changed",
    "init_global",
    "verification_panel",
]

# Nombre legible de cada evento (la lista y la cabecera del detalle)
_EVENT_TITLES_SRC = {
    "on_app_start": QT_TRANSLATE_NOOP("EventsTab", "Al abrir la aplicación"),
    "on_app_end": QT_TRANSLATE_NOOP("EventsTab", "Al cerrar la aplicación"),
    "on_import": QT_TRANSLATE_NOOP("EventsTab", "Al importar"),
    "on_scan_complete": QT_TRANSLATE_NOOP("EventsTab", "Al terminar el proceso"),
    "on_transfer_validate": QT_TRANSLATE_NOOP("EventsTab", "Antes de transferir"),
    "on_transfer_advanced": QT_TRANSLATE_NOOP("EventsTab", "Transferencia avanzada"),
    "on_transfer_page": QT_TRANSLATE_NOOP("EventsTab", "Al transferir cada página"),
    "on_navigate_prev": QT_TRANSLATE_NOOP("EventsTab", "Navegar a la anterior"),
    "on_navigate_next": QT_TRANSLATE_NOOP("EventsTab", "Navegar a la siguiente"),
    "on_navigate_script": QT_TRANSLATE_NOOP("EventsTab", "Botón de navegación"),
    "on_key_event": QT_TRANSLATE_NOOP("EventsTab", "Al pulsar una tecla"),
    "on_batch_loaded": QT_TRANSLATE_NOOP("EventsTab", "Al abrir un lote"),
    "on_page_changed": QT_TRANSLATE_NOOP("EventsTab", "Al cambiar de página"),
    "init_global": QT_TRANSLATE_NOOP("EventsTab", "Al iniciar el programa"),
    "verification_panel": QT_TRANSLATE_NOOP("EventsTab", "Panel de verificación"),
}

_EVENT_DESCRIPTIONS_SRC = {
    "on_app_start": QT_TRANSLATE_NOOP("EventsTab", "Al abrir la aplicación"),
    "on_app_end": QT_TRANSLATE_NOOP("EventsTab", "Al cerrar la aplicación"),
    "on_import": QT_TRANSLATE_NOOP(
        "EventsTab", "Al pulsar Procesar (reemplaza carga estándar si está definido)"
    ),
    "on_scan_complete": QT_TRANSLATE_NOOP(
        "EventsTab", "Al terminar carga + todo el pipeline"
    ),
    "on_transfer_validate": QT_TRANSLATE_NOOP(
        "EventsTab", "Antes de transferir; retornar False cancela"
    ),
    "on_transfer_advanced": QT_TRANSLATE_NOOP(
        "EventsTab", "Transferencia avanzada scripteada"
    ),
    "on_transfer_page": QT_TRANSLATE_NOOP("EventsTab", "Post-copia por página"),
    "on_navigate_prev": QT_TRANSLATE_NOOP("EventsTab", "Navegación previa programable"),
    "on_navigate_next": QT_TRANSLATE_NOOP(
        "EventsTab", "Navegación siguiente programable"
    ),
    "on_navigate_script": QT_TRANSLATE_NOOP(
        "EventsTab", "Botón de navegación programable del visor"
    ),
    "on_key_event": QT_TRANSLATE_NOOP("EventsTab", "Tecla personalizada"),
    "on_batch_loaded": QT_TRANSLATE_NOOP(
        "EventsTab", "Al abrir un lote en el Workbench"
    ),
    "on_page_changed": QT_TRANSLATE_NOOP(
        "EventsTab", "Tras navegar a otra página del lote"
    ),
    "init_global": QT_TRANSLATE_NOOP(
        "EventsTab", "Al iniciar el programa (script global del launcher)"
    ),
    "verification_panel": QT_TRANSLATE_NOOP(
        "EventsTab", "Panel de verificación (clase VerificationPanel)"
    ),
}

_tr_evt = lambda s: QCoreApplication.translate("EventsTab", s)

# Alto de cada fila de la lista de eventos
ROW_HEIGHT = 48

# Estados del punto y de la píldora de cada evento
STATE_EMPTY = "empty"
STATE_ACTIVE = "active"
STATE_PAUSED = "paused"


def EVENT_DESCRIPTIONS() -> dict[str, str]:
    """Devuelve descripciones de eventos traducidas."""
    return {k: _tr_evt(v) for k, v in _EVENT_DESCRIPTIONS_SRC.items()}


def EVENT_TITLES() -> dict[str, str]:
    """Devuelve los nombres legibles de los eventos, traducidos."""
    return {k: _tr_evt(v) for k, v in _EVENT_TITLES_SRC.items()}


def _repolish(widget: QWidget) -> None:
    """Reaplica el QSS tras cambiar una propiedad dinámica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class _EventRow(QWidget):
    """Fila de la lista: punto de estado, nombres y píldora ACTIVO/PAUSADO."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("eventRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._dot = QLabel()
        self._dot.setObjectName("eventDot")
        self._dot.setFixedSize(10, 10)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        names = QVBoxLayout()
        names.setSpacing(0)
        self._lbl_title = QLabel(EVENT_TITLES().get(name, name))
        self._lbl_title.setObjectName("eventRowName")
        names.addWidget(self._lbl_title)
        lbl_canonical = QLabel(name)
        lbl_canonical.setObjectName("eventCanonical")
        names.addWidget(lbl_canonical)
        layout.addLayout(names, 1)

        self._pill = QLabel()
        self._pill.setObjectName("eventPill")
        layout.addWidget(self._pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set_state(STATE_EMPTY)

    def set_state(self, state: str) -> None:
        self.state = state
        for w in (self._dot, self._lbl_title, self._pill):
            w.setProperty("state", state)
            _repolish(w)
        self._pill.setText(
            {
                STATE_ACTIVE: self.tr("ACTIVO"),
                STATE_PAUSED: self.tr("PAUSADO"),
            }.get(state, "")
        )
        self._pill.setVisible(state != STATE_EMPTY)


class EventsTab(QWidget):
    """Editor de entry points de ciclo de vida."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Entradas tal cual vienen de events_json (str o dict), para
        # conservar al guardar las claves que esta pestaña no edita.
        self._events: dict[str, Any] = {}
        self._codes: dict[str, str] = {}
        self._enabled: dict[str, bool] = {}
        self._current_event: str = ""
        self._rows: dict[str, _EventRow] = {}
        self._setup_ui()
        self._load_from_app(app)

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # --- Lista de eventos ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        lbl_list = QLabel(self.tr("EVENTOS DEL CICLO DE VIDA"))
        lbl_list.setObjectName("sectionTitle")
        left_layout.addWidget(lbl_list)
        self._event_list = QListWidget()
        self._event_list.setObjectName("eventList")
        self._event_list.setToolTip(
            self.tr("Seleccionar el evento del ciclo de vida a editar")
        )
        for name in EVENT_NAMES:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            row = _EventRow(name)
            # Alto fijo: el sizeHint previo al QSS se queda corto y corta
            # los guiones bajos del nombre canónico
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self._event_list.addItem(item)
            self._event_list.setItemWidget(item, row)
            self._rows[name] = row
        left_layout.addWidget(self._event_list)
        splitter.addWidget(left)

        # --- Detalle del evento ---
        detail = QFrame()
        detail.setObjectName("eventDetail")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(12, 4, 4, 4)
        dl.setSpacing(6)

        self._lbl_title = QLabel()
        self._lbl_title.setObjectName("eventTitle")
        dl.addWidget(self._lbl_title)
        self._lbl_description = QLabel()
        self._lbl_description.setProperty("cssClass", "subtitle")
        self._lbl_description.setWordWrap(True)
        dl.addWidget(self._lbl_description)
        self._lbl_canonical = QLabel()
        self._lbl_canonical.setObjectName("eventCanonical")
        dl.addWidget(self._lbl_canonical)

        self._chk_enabled = QCheckBox(self.tr("Activado"))
        self._chk_enabled.setToolTip(
            self.tr(
                "Si se desactiva, el script no se ejecuta aunque tenga código "
                "(evento PAUSADO). Útil para depurar sin borrarlo"
            )
        )
        self._chk_enabled.toggled.connect(self._on_enabled_toggled)
        dl.addWidget(self._chk_enabled)

        code_bar = QHBoxLayout()
        lbl_code = QLabel(self.tr("CÓDIGO PYTHON"))
        lbl_code.setObjectName("sectionTitle")
        code_bar.addWidget(lbl_code)
        code_bar.addStretch(1)
        self._btn_edit = QPushButton(self.tr("Editar script…"))
        self._btn_edit.setProperty("cssClass", "primary")
        self._btn_edit.setToolTip(
            self.tr("Abrir el editor del script con las variables disponibles")
        )
        self._btn_edit.clicked.connect(self._open_script_dialog)
        code_bar.addWidget(self._btn_edit)
        dl.addLayout(code_bar)

        # Resumen de solo lectura: el código se edita en el diálogo
        self._code_edit = CodeEditor(read_only=True)
        self._code_edit.setToolTip(self.tr("Doble clic para editar el script"))
        self._code_edit.mouseDoubleClickEvent = lambda _e: self._open_script_dialog()
        dl.addWidget(self._code_edit, 1)
        splitter.addWidget(detail)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 560])

        self._event_list.currentItemChanged.connect(self._on_current_item_changed)

    def _placeholder_for(self, event_name: str | None) -> str:
        """Esqueleto Python a mostrar como placeholder para ``event_name``.

        Usa la firma documentada en ``EVENT_SIGNATURES`` (compartida con el
        asistente AI). Cae al de ``on_app_start`` si el evento no tiene
        firma específica. Reemplaza el docstring de la firma por ``pass``
        para que sea un esqueleto ejecutable.
        """
        sig = EVENT_SIGNATURES.get(event_name or "")
        if not sig:
            sig = EVENT_SIGNATURES["on_app_start"]
        head = sig.split("\n", 1)[0]
        return f"{head}\n    pass"

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _load_from_app(self, app: Application) -> None:
        self._events = parse_events(app.events_json)
        for name, config in self._events.items():
            self._codes[name] = event_source(config)
            self._enabled[name] = event_enabled(config)
        for name in EVENT_NAMES:
            self._refresh_row(name)

        # Se abre en el primer evento con código: una App que solo define
        # on_transfer_validate se abría en on_app_start, vacío.
        first = next(
            (n for n in EVENT_NAMES if self._codes.get(n, "").strip()),
            EVENT_NAMES[0],
        )
        self.select_event(first)

    def state_of(self, name: str) -> str:
        """Estado del evento: sin script, ACTIVO o PAUSADO."""
        if not self._codes.get(name, "").strip():
            return STATE_EMPTY
        return STATE_ACTIVE if self._enabled.get(name, True) else STATE_PAUSED

    def _refresh_row(self, name: str) -> None:
        row = self._rows.get(name)
        if row is not None:
            row.set_state(self.state_of(name))

    def select_event(self, name: str) -> None:
        """Selecciona ``name`` en la lista y carga su detalle."""
        for i in range(self._event_list.count()):
            item = self._event_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self._event_list.setCurrentItem(item)
                return

    def _on_current_item_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        self._current_event = name
        self._lbl_title.setText(EVENT_TITLES().get(name, name))
        self._lbl_description.setText(EVENT_DESCRIPTIONS().get(name, ""))
        self._lbl_canonical.setText(name)
        self._show_code(name)

    def _show_code(self, name: str) -> None:
        code = self._codes.get(name, "")
        self._code_edit.setPlainText(code)
        self._code_edit.setPlaceholderText(self._placeholder_for(name))
        self._chk_enabled.blockSignals(True)
        self._chk_enabled.setChecked(self._enabled.get(name, True))
        self._chk_enabled.blockSignals(False)
        # Sin código no hay nada que activar o pausar
        self._chk_enabled.setEnabled(bool(code.strip()))

    def set_event_code(self, name: str, code: str) -> None:
        """Cambia el código de un evento (lo que hace «Guardar» del diálogo)."""
        self._codes[name] = code
        self._enabled.setdefault(name, True)
        self._refresh_row(name)
        if name == self._current_event:
            self._show_code(name)

    def _on_enabled_toggled(self, checked: bool) -> None:
        if not self._current_event:
            return
        self._enabled[self._current_event] = checked
        self._refresh_row(self._current_event)

    def _open_script_dialog(self) -> None:
        name = self._current_event
        if not name:
            return
        dialog = EventScriptDialog(
            name,
            EVENT_TITLES().get(name, name),
            self._codes.get(name, ""),
            self._placeholder_for(name),
            parent=self,
        )
        if dialog.exec():
            self.set_event_code(name, dialog.code())

    def apply_to(self, app: Application) -> None:
        """Guarda los eventos en el JSON de la aplicación."""
        events: dict[str, Any] = {}
        # Las claves que esta pestaña no muestra se conservan tal cual
        names = list(self._events) + [n for n in self._codes if n not in self._events]
        for name in names:
            previous = self._events.get(name)
            code = self._codes.get(name, event_source(previous))
            if not code.strip():
                continue
            events[name] = make_event_entry(
                previous, code, self._enabled.get(name, True)
            )
        app.events_json = json.dumps(events)
