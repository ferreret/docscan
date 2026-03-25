"""Widget de preview para cambios propuestos por el asistente AI MODE.

Muestra un resumen estructurado del cambio con Aceptar/Rechazar.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

_ctx = "AppChangePreview"

_LABEL_ACCEPT = QT_TRANSLATE_NOOP(_ctx, "Aceptar")
_LABEL_REJECT = QT_TRANSLATE_NOOP(_ctx, "Rechazar")
_LABEL_CONFIRM_DELETE = QT_TRANSLATE_NOOP(_ctx, "Confirmar eliminacion")
_LABEL_CANCEL = QT_TRANSLATE_NOOP(_ctx, "Cancelar")

_tr = lambda s: QCoreApplication.translate(_ctx, s)


def _pipeline_summary(steps: list[dict]) -> str:
    """Genera un resumen de los pasos del pipeline."""
    lines = []
    for i, step in enumerate(steps, 1):
        stype = step.get("type", "?")
        if stype == "image_op":
            lines.append(f"  {i}. Imagen: {step.get('op', '?')}")
        elif stype == "barcode":
            syms = ", ".join(step.get("symbologies", [])[:3]) or "todas"
            lines.append(f"  {i}. Barcode: {step.get('engine', '?')} ({syms})")
        elif stype == "ocr":
            langs = ", ".join(step.get("languages", []))
            lines.append(f"  {i}. OCR: {step.get('engine', '?')} [{langs}]")
        elif stype == "script":
            label = step.get("label") or step.get("entry_point") or "script"
            lines.append(f"  {i}. Script: {label}")
    return "\n".join(lines) if lines else "  (vacio)"


def _events_summary(events: dict) -> str:
    """Resumen de los eventos con codigo."""
    if not events:
        return "  (ninguno)"
    return "\n".join(f"  - {name}" for name in events if events[name].strip())


def _fields_summary(fields: list[dict]) -> str:
    """Resumen de campos de lote."""
    if not fields:
        return "  (ninguno)"
    return "\n".join(
        f"  - {f.get('label', '?')} ({f.get('type', '?')})"
        for f in fields
    )


class AppChangePreview(QFrame):
    """Preview de un cambio propuesto.

    Signals:
        accepted: Con el tool_input original.
        rejected: Sin datos.
    """

    accepted = Signal(dict)
    rejected = Signal()

    def __init__(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        explanation: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._explanation = explanation
        self.setObjectName("appChangePreview")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Titulo segun tipo de operacion
        title = self._get_title()
        title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_label)

        # Explicacion
        if self._explanation:
            exp_label = QLabel(self._explanation)
            exp_label.setWordWrap(True)
            exp_label.setStyleSheet("color: gray; font-style: italic;")
            layout.addWidget(exp_label)

        # Contenido segun tipo
        content = self._build_content()
        if content:
            content_label = QLabel(content)
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                content_label.textInteractionFlags()
                | content_label.textInteractionFlags().TextSelectableByMouse
            )
            layout.addWidget(content_label)

        # Preview de codigo si hay eventos o scripts
        code_preview = self._get_code_preview()
        if code_preview:
            code_edit = QPlainTextEdit()
            code_edit.setReadOnly(True)
            code_edit.setPlainText(code_preview)
            code_edit.setFont(QFont("monospace", 9))
            code_edit.setMaximumHeight(150)
            layout.addWidget(code_edit)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self._tool_name == "delete_application":
            btn_accept = QPushButton(_tr(_LABEL_CONFIRM_DELETE))
            btn_accept.setObjectName("diffRejectBtn")  # rojo
            btn_reject = QPushButton(_tr(_LABEL_CANCEL))
        else:
            btn_accept = QPushButton(_tr(_LABEL_ACCEPT))
            btn_accept.setObjectName("diffAcceptBtn")
            btn_reject = QPushButton(_tr(_LABEL_REJECT))

        btn_accept.clicked.connect(lambda: self.accepted.emit(self._tool_input))
        btn_reject.clicked.connect(self.rejected.emit)
        btn_layout.addWidget(btn_accept)
        btn_layout.addWidget(btn_reject)
        layout.addLayout(btn_layout)

    def _get_title(self) -> str:
        titles = {
            "create_application": f"Crear aplicacion: {self._tool_input.get('name', '?')}",
            "update_application": f"Modificar: {self._tool_input.get('app_name', '?')}",
            "duplicate_application": (
                f"Duplicar: {self._tool_input.get('source_app_name', '?')} "
                f"→ {self._tool_input.get('new_name', '?')}"
            ),
            "delete_application": f"ELIMINAR: {self._tool_input.get('app_name', '?')}",
            "set_event_code": (
                f"Evento {self._tool_input.get('event_name', '?')} "
                f"en {self._tool_input.get('app_name', '?')}"
            ),
        }
        return titles.get(self._tool_name, self._tool_name)

    def _build_content(self) -> str:
        ti = self._tool_input
        lines = []

        if self._tool_name == "delete_application":
            lines.append("Esta accion eliminara la aplicacion y TODOS sus lotes.")
            lines.append("Esta accion es IRREVERSIBLE.")
            return "\n".join(lines)

        if self._tool_name == "set_event_code":
            return ""  # El codigo se muestra en el preview

        # Para create/update/duplicate
        if "description" in ti and ti["description"]:
            lines.append(f"Descripcion: {ti['description']}")

        if "pipeline" in ti:
            lines.append(f"\nPipeline ({len(ti['pipeline'])} pasos):")
            lines.append(_pipeline_summary(ti["pipeline"]))

        if "events" in ti:
            lines.append(f"\nEventos:")
            lines.append(_events_summary(ti["events"]))

        if "batch_fields" in ti:
            lines.append(f"\nCampos de lote:")
            lines.append(_fields_summary(ti["batch_fields"]))

        general = ti.get("general", {})
        if general:
            parts = []
            if "auto_transfer" in general:
                parts.append(f"auto-transfer={'si' if general['auto_transfer'] else 'no'}")
            if "output_format" in general:
                parts.append(f"formato={general['output_format']}")
            if parts:
                lines.append(f"\nGeneral: {', '.join(parts)}")

        image = ti.get("image_config", {})
        if image:
            parts = []
            if "format" in image:
                parts.append(f"formato={image['format']}")
            if "color_mode" in image:
                parts.append(f"color={image['color_mode']}")
            if parts:
                lines.append(f"Imagen: {', '.join(parts)}")

        return "\n".join(lines) if lines else ""

    def _get_code_preview(self) -> str | None:
        if self._tool_name == "set_event_code":
            return self._tool_input.get("code")

        # Mostrar codigo del primer script en pipeline
        pipeline = self._tool_input.get("pipeline", [])
        scripts = [s for s in pipeline if s.get("type") == "script" and s.get("script")]
        if scripts:
            first = scripts[0]
            label = first.get("label") or first.get("entry_point") or "script"
            return f"# {label}\n{first['script']}"
        return None

    def set_enabled_state(self, enabled: bool) -> None:
        """Deshabilita botones tras aceptar/rechazar."""
        self.setEnabled(enabled)
