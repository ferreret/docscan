"""Widget de diff visual para propuestas de pipeline.

Muestra una comparacion antes/despues con colores:
verde = paso nuevo, rojo = paso eliminado, amarillo = modificado.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.steps import (
    BarcodeStep,
    ImageOpStep,
    OcrStep,
    PipelineStep,
    ScriptStep,
)

log = logging.getLogger(__name__)

_ctx = "PipelineDiffWidget"

_LABEL_ACTUAL = QT_TRANSLATE_NOOP(_ctx, "Actual")
_LABEL_PROPOSED = QT_TRANSLATE_NOOP(_ctx, "Propuesto")
_LABEL_ACCEPT = QT_TRANSLATE_NOOP(_ctx, "Aceptar")
_LABEL_REJECT = QT_TRANSLATE_NOOP(_ctx, "Rechazar")
_LABEL_ADDED = QT_TRANSLATE_NOOP(_ctx, "(nuevo)")
_LABEL_REMOVED = QT_TRANSLATE_NOOP(_ctx, "(eliminado)")

_tr = lambda s: QCoreApplication.translate(_ctx, s)

# Colores para diff
_COLOR_ADDED = QColor(76, 175, 80, 40)       # verde suave
_COLOR_REMOVED = QColor(244, 67, 54, 40)     # rojo suave
_COLOR_MODIFIED = QColor(255, 193, 7, 40)    # amarillo suave
_COLOR_UNCHANGED = QColor(0, 0, 0, 0)        # transparente

_TEXT_ADDED = QColor(46, 125, 50)
_TEXT_REMOVED = QColor(198, 40, 40)
_TEXT_MODIFIED = QColor(230, 150, 0)


def step_summary(step: PipelineStep) -> str:
    """Resumen corto de un paso para mostrar en la lista."""
    prefix = "+" if step.enabled else "-"
    if isinstance(step, ImageOpStep):
        return f"[{prefix}] Imagen: {step.op}"
    elif isinstance(step, BarcodeStep):
        syms = ", ".join(step.symbologies[:3]) or "todas"
        return f"[{prefix}] Barcode: {step.engine} · {syms}"
    elif isinstance(step, OcrStep):
        langs = ", ".join(step.languages)
        return f"[{prefix}] OCR: {step.engine} · {langs}"
    elif isinstance(step, ScriptStep):
        label = step.label or step.entry_point or "script"
        return f"[{prefix}] Script: {label}"
    return f"[{prefix}] {step.type}"


def _step_key(step: PipelineStep) -> str:
    """Clave para comparar pasos (tipo + campos distintivos)."""
    if isinstance(step, ImageOpStep):
        return f"image_op:{step.op}"
    elif isinstance(step, BarcodeStep):
        return f"barcode:{step.engine}:{','.join(step.symbologies)}"
    elif isinstance(step, OcrStep):
        return f"ocr:{step.engine}:{','.join(step.languages)}"
    elif isinstance(step, ScriptStep):
        return f"script:{step.label}:{step.entry_point}"
    return f"{step.type}"


def _steps_equal(a: PipelineStep, b: PipelineStep) -> bool:
    """Compara dos pasos ignorando el id."""
    da = asdict(a)
    db = asdict(b)
    da.pop("id", None)
    db.pop("id", None)
    return da == db


def compute_diff(
    current: list[PipelineStep],
    proposed: list[PipelineStep],
) -> list[dict[str, Any]]:
    """Computa el diff entre dos listas de pasos.

    Returns:
        Lista de dicts con: step, status ('added', 'removed', 'modified', 'unchanged'),
        side ('current', 'proposed', 'both').
    """
    result: list[dict[str, Any]] = []

    # Indexar pasos actuales por posicion
    max_len = max(len(current), len(proposed))

    # Mapear pasos por key para detectar movidos/modificados
    current_keys = {_step_key(s): i for i, s in enumerate(current)}

    matched_current: set[int] = set()
    matched_proposed: set[int] = set()

    # Primer pase: emparejar por posicion + tipo similar
    for pi, pstep in enumerate(proposed):
        pkey = _step_key(pstep)
        if pi < len(current):
            cstep = current[pi]
            if _step_key(cstep) == pkey:
                matched_current.add(pi)
                matched_proposed.add(pi)
                if _steps_equal(cstep, pstep):
                    result.append({
                        "current": cstep,
                        "proposed": pstep,
                        "status": "unchanged",
                    })
                else:
                    result.append({
                        "current": cstep,
                        "proposed": pstep,
                        "status": "modified",
                    })
                continue

        # Buscar por key en current
        if pkey in current_keys:
            ci = current_keys[pkey]
            if ci not in matched_current:
                matched_current.add(ci)
                matched_proposed.add(pi)
                cstep = current[ci]
                if _steps_equal(cstep, pstep):
                    result.append({
                        "current": cstep,
                        "proposed": pstep,
                        "status": "unchanged",
                    })
                else:
                    result.append({
                        "current": cstep,
                        "proposed": pstep,
                        "status": "modified",
                    })
                continue

        # Nuevo paso
        matched_proposed.add(pi)
        result.append({
            "current": None,
            "proposed": pstep,
            "status": "added",
        })

    # Pasos eliminados (en current pero no emparejados)
    for ci, cstep in enumerate(current):
        if ci not in matched_current:
            result.append({
                "current": cstep,
                "proposed": None,
                "status": "removed",
            })

    return result


class PipelineDiffWidget(QFrame):
    """Widget que muestra diff visual de pipeline.

    Signals:
        accepted: Emitida cuando el usuario acepta la propuesta.
        rejected: Emitida cuando el usuario rechaza la propuesta.
    """

    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        current_steps: list[PipelineStep],
        proposed_steps: list[PipelineStep],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pipelineDiffWidget")
        self._current = current_steps
        self._proposed = proposed_steps
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Cabeceras
        header = QHBoxLayout()
        lbl_current = QLabel(f"<b>{_tr(_LABEL_ACTUAL)}</b>")
        lbl_proposed = QLabel(f"<b>{_tr(_LABEL_PROPOSED)}</b>")
        header.addWidget(lbl_current)
        header.addWidget(lbl_proposed)
        layout.addLayout(header)

        # Listas lado a lado
        lists_layout = QHBoxLayout()
        self._list_current = QListWidget()
        self._list_proposed = QListWidget()
        self._list_current.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list_proposed.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        lists_layout.addWidget(self._list_current)
        lists_layout.addWidget(self._list_proposed)
        layout.addLayout(lists_layout)

        # Botones
        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_accept = QPushButton(_tr(_LABEL_ACCEPT))
        self._btn_reject = QPushButton(_tr(_LABEL_REJECT))
        self._btn_accept.setObjectName("diffAcceptBtn")
        self._btn_reject.setObjectName("diffRejectBtn")
        buttons.addWidget(self._btn_accept)
        buttons.addWidget(self._btn_reject)
        layout.addLayout(buttons)

        self._btn_accept.clicked.connect(self.accepted.emit)
        self._btn_reject.clicked.connect(self.rejected.emit)

        self._populate()

    def _populate(self) -> None:
        """Rellena ambas listas con el diff."""
        diff = compute_diff(self._current, self._proposed)

        for entry in diff:
            status = entry["status"]
            current_step = entry.get("current")
            proposed_step = entry.get("proposed")

            if status == "added":
                # Lado izquierdo vacio, lado derecho verde
                empty_item = QListWidgetItem("")
                self._list_current.addItem(empty_item)

                text = f"{step_summary(proposed_step)} {_tr(_LABEL_ADDED)}"
                item = QListWidgetItem(text)
                item.setBackground(_COLOR_ADDED)
                item.setForeground(_TEXT_ADDED)
                self._list_proposed.addItem(item)

            elif status == "removed":
                # Lado izquierdo rojo, lado derecho vacio
                text = f"{step_summary(current_step)} {_tr(_LABEL_REMOVED)}"
                item = QListWidgetItem(text)
                item.setBackground(_COLOR_REMOVED)
                item.setForeground(_TEXT_REMOVED)
                self._list_current.addItem(item)

                empty_item = QListWidgetItem("")
                self._list_proposed.addItem(empty_item)

            elif status == "modified":
                # Ambos lados amarillos
                item_c = QListWidgetItem(step_summary(current_step))
                item_c.setBackground(_COLOR_MODIFIED)
                item_c.setForeground(_TEXT_MODIFIED)
                self._list_current.addItem(item_c)

                item_p = QListWidgetItem(step_summary(proposed_step))
                item_p.setBackground(_COLOR_MODIFIED)
                item_p.setForeground(_TEXT_MODIFIED)
                self._list_proposed.addItem(item_p)

            else:  # unchanged
                item_c = QListWidgetItem(step_summary(current_step))
                self._list_current.addItem(item_c)

                item_p = QListWidgetItem(step_summary(proposed_step))
                self._list_proposed.addItem(item_p)
