"""Diálogo «Editar script…» de un evento del ciclo de vida.

Es el ``ScriptEditorDialog`` de FlexibarNET10: el editor de código con
colores y números de línea y, al lado, el panel de variables disponibles para
ese evento (sacadas de su firma en ``EVENT_SIGNATURES``). Guardar devuelve el
código a la pestaña Eventos; Cancelar lo descarta.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.services._assistant_constants import EVENT_SIGNATURES
from app.services.external_editor_service import detect_editor, edit_script
from app.ui.widgets.code_editor import CodeEditor

# Qué es cada parámetro de los eventos (los nombres salen de la firma)
_PARAM_DESCRIPTIONS_SRC = {
    "app": QT_TRANSLATE_NOOP("EventScriptDialog", "Aplicación activa (id, name)"),
    "batch": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Lote actual (id, state, fields, page_count)"
    ),
    "page": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Página activa (fields, barcodes, ocr_text)"
    ),
    "pages": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Páginas del lote (barcodes, fields, separadores)"
    ),
    "documents": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Documentos lógicos (index, separator_value, pages)"
    ),
    "result": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Resultado de la transferencia simple"
    ),
    "page_index": QT_TRANSLATE_NOOP("EventScriptDialog", "Índice de la página"),
    "current_page_index": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "Índice de la página actual"
    ),
    "total_pages": QT_TRANSLATE_NOOP("EventScriptDialog", "Número de páginas"),
    "success": QT_TRANSLATE_NOOP(
        "EventScriptDialog", "True si la página se copió bien"
    ),
    "key": QT_TRANSLATE_NOOP("EventScriptDialog", "Nombre de la tecla pulsada"),
}

# Lo que el motor de scripts inyecta siempre (CLAUDE.md, «Script context»)
_BUILTINS_SRC = [
    ("log", QT_TRANSLATE_NOOP("EventScriptDialog", "Log de la aplicación")),
    ("http", QT_TRANSLATE_NOOP("EventScriptDialog", "Cliente httpx")),
    ("re", QT_TRANSLATE_NOOP("EventScriptDialog", "Expresiones regulares")),
    ("json", QT_TRANSLATE_NOOP("EventScriptDialog", "Módulo json")),
    ("datetime", QT_TRANSLATE_NOOP("EventScriptDialog", "Fechas y horas")),
    ("Path", QT_TRANSLATE_NOOP("EventScriptDialog", "Rutas (pathlib)")),
]

_SIGNATURE = re.compile(r"^\s*def\s+\w+\((?P<params>[^)]*)\)")


def _tr(text: str) -> str:
    return QCoreApplication.translate("EventScriptDialog", text)


def signature_line(event_name: str) -> str:
    """Primera línea de la firma documentada del evento ("" si no hay)."""
    sig = EVENT_SIGNATURES.get(event_name, "")
    return sig.split("\n", 1)[0] if sig else ""


def available_variables(event_name: str) -> list[tuple[str, str]]:
    """Pares (variable, descripción) que recibe el script del evento.

    Los parámetros salen de la firma de ``EVENT_SIGNATURES``; detrás van los
    módulos que inyecta siempre el motor de scripts.
    """
    params: list[str] = []
    match = _SIGNATURE.match(signature_line(event_name))
    if match:
        params = [
            p.split(":")[0].split("=")[0].strip()
            for p in match.group("params").split(",")
            if p.strip()
        ]
    variables = [(p, _tr(_PARAM_DESCRIPTIONS_SRC.get(p, ""))) for p in params]
    variables += [(name, _tr(desc)) for name, desc in _BUILTINS_SRC]
    return variables


class _EditorWorker(QThread):
    """Hilo para la edición bloqueante en VS Code."""

    finished = Signal(object)  # str | None

    def __init__(self, code: str, event_name: str) -> None:
        super().__init__()
        self._code = code
        self._event_name = event_name

    def run(self) -> None:
        result = edit_script(self._code, "event", self._event_name)
        self.finished.emit(result)


class EventScriptDialog(QDialog):
    """Editor del script de un evento con el panel de variables disponibles.

    Args:
        event_name: Nombre canónico del evento (``on_transfer_validate``).
        title: Nombre legible («Antes de transferir»).
        code: Código actual del evento.
        placeholder: Esqueleto que se ve con el editor vacío.
    """

    def __init__(
        self,
        event_name: str,
        title: str,
        code: str,
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._event_name = event_name
        self._editor_worker: _EditorWorker | None = None
        self.setWindowTitle(self.tr("Editar script — {0}").format(title))
        self.setMinimumSize(820, 540)
        self.resize(980, 640)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setObjectName("eventTitle")
        header.addWidget(lbl_title)
        lbl_canonical = QLabel(event_name)
        lbl_canonical.setObjectName("eventCanonical")
        header.addWidget(lbl_canonical)
        header.addStretch(1)
        self._btn_vscode = QPushButton(self.tr("Abrir en VS Code"))
        self._btn_vscode.setToolTip(
            self.tr("Editar el código en VS Code con autocompletado y sintaxis")
        )
        self._btn_vscode.setVisible(detect_editor() is not None)
        self._btn_vscode.clicked.connect(self._open_in_vscode)
        header.addWidget(self._btn_vscode)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._code_edit = CodeEditor()
        self._code_edit.setPlainText(code)
        self._code_edit.setPlaceholderText(placeholder)
        splitter.addWidget(self._code_edit)
        splitter.addWidget(self._build_variables_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 260])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.tr("Guardar"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self.tr("Cancelar")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_variables_panel(self) -> QWidget:
        """Panel «Variables disponibles»: firma y una fila por variable."""
        panel = QFrame()
        panel.setObjectName("variablesPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        title = QLabel(self.tr("VARIABLES DISPONIBLES"))
        title.setObjectName("sectionTitle")
        outer.addWidget(title)

        sig = signature_line(self._event_name)
        if sig:
            lbl_sig = QLabel(sig)
            lbl_sig.setObjectName("eventSignature")
            lbl_sig.setWordWrap(True)
            lbl_sig.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            outer.addWidget(lbl_sig)

        body = QWidget()
        body.setObjectName("variablesBody")
        rows = QVBoxLayout(body)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)
        self._variable_names: list[str] = []
        for name, desc in available_variables(self._event_name):
            self._variable_names.append(name)
            row = QVBoxLayout()
            row.setSpacing(0)
            lbl_name = QLabel(name)
            lbl_name.setObjectName("variableName")
            row.addWidget(lbl_name)
            if desc:
                lbl_desc = QLabel(desc)
                lbl_desc.setObjectName("fieldType")
                lbl_desc.setWordWrap(True)
                row.addWidget(lbl_desc)
            rows.addLayout(row)
        rows.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("sectionBody")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        return panel

    def code(self) -> str:
        """Código del editor."""
        return self._code_edit.toPlainText()

    def _open_in_vscode(self) -> None:
        """Lanza VS Code para editar el script."""
        self._btn_vscode.setEnabled(False)
        self._btn_vscode.setText(self.tr("Editando en VS Code..."))
        self._editor_worker = _EditorWorker(self.code(), self._event_name)
        self._editor_worker.finished.connect(self._on_editor_done)
        self._editor_worker.start()

    def _on_editor_done(self, result: str | None) -> None:
        """Actualiza el código al volver de VS Code."""
        self._btn_vscode.setEnabled(True)
        self._btn_vscode.setText(self.tr("Abrir en VS Code"))
        if result is not None:
            self._code_edit.setPlainText(result)
