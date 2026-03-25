"""Dialogo de resultados de prueba de pipeline.

Muestra el resultado por paso: imagen intermedia, barcodes,
texto OCR, campos y errores.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.pipeline.steps import PipelineStep
from app.pipeline.test_executor import StepSnapshot
from app.ui.workbench.page_state import ndarray_to_qpixmap

log = logging.getLogger(__name__)

_MAX_THUMB_H = 200


def _step_label(step: PipelineStep) -> str:
    """Genera etiqueta legible para un paso."""
    type_labels = {
        "image_op": "Imagen",
        "barcode": "Barcode",
        "ocr": "OCR",
        "script": "Script",
    }
    prefix = type_labels.get(step.type, step.type)
    detail = getattr(step, "op", None) or getattr(step, "label", None) or step.id
    return f"{prefix}: {detail}"


def _image_thumbnail(image: np.ndarray, max_h: int = _MAX_THUMB_H) -> QPixmap:
    """Convierte ndarray a QPixmap escalado."""
    pixmap = ndarray_to_qpixmap(image)
    if pixmap.height() > max_h:
        pixmap = pixmap.scaledToHeight(max_h, Qt.TransformationMode.SmoothTransformation)
    return pixmap


class TestPipelineResultDialog(QDialog):
    """Muestra los resultados paso a paso de una prueba de pipeline."""

    def __init__(
        self,
        snapshots: list[StepSnapshot],
        original_image: np.ndarray | None = None,
        source_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Resultado de prueba de pipeline"))
        self.setMinimumSize(700, 500)
        self.resize(850, 650)
        self._build_ui(snapshots, original_image, source_name)

    def _build_ui(
        self,
        snapshots: list[StepSnapshot],
        original_image: np.ndarray | None,
        source_name: str,
    ) -> None:
        layout = QVBoxLayout(self)

        # Header
        if original_image is not None:
            h, w = original_image.shape[:2]
            header_text = self.tr(
                "Imagen: {0} — {1}x{2} px — {3} pasos ejecutados"
            ).format(source_name or "?", w, h, len(snapshots))
        else:
            header_text = self.tr("{0} pasos ejecutados").format(len(snapshots))
        header = QLabel(f"<b>{header_text}</b>")
        layout.addWidget(header)

        # Scroll area con cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        cards_layout.setSpacing(8)

        for i, snap in enumerate(snapshots):
            card = self._build_step_card(i + 1, snap)
            cards_layout.addWidget(card)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Resumen final
        n_errors = sum(1 for s in snapshots if s.error)
        n_barcodes = len(snapshots[-1].barcodes) if snapshots else 0
        n_fields = len(snapshots[-1].fields) if snapshots else 0
        total_ms = sum(s.elapsed_ms for s in snapshots)
        summary = self.tr(
            "Total: {0} barcodes, {1} campos, {2} errores — {3:.0f} ms"
        ).format(n_barcodes, n_fields, n_errors, total_ms)
        summary_label = QLabel(summary)
        if n_errors > 0:
            summary_label.setStyleSheet("color: #e53935; font-weight: bold;")
        layout.addWidget(summary_label)

        # Boton cerrar
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_step_card(self, num: int, snap: StepSnapshot) -> QGroupBox:
        """Construye un QGroupBox con los resultados de un paso."""
        title = f"{num}. {_step_label(snap.step)}"
        if snap.error:
            title += " — ERROR"
        title += f"  ({snap.elapsed_ms:.0f} ms)"

        group = QGroupBox(title)
        if snap.error:
            group.setStyleSheet("QGroupBox { border: 2px solid #e53935; }")
        glayout = QVBoxLayout(group)
        glayout.setContentsMargins(6, 12, 6, 6)
        glayout.setSpacing(4)

        # Error
        if snap.error:
            err_label = QLabel(snap.error)
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #e53935;")
            glayout.addWidget(err_label)

        # Imagen (para image_op y siempre que haya imagen)
        if snap.step.type == "image_op" and snap.image is not None:
            img_label = QLabel()
            img_label.setPixmap(_image_thumbnail(snap.image))
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h, w = snap.image.shape[:2]
            glayout.addWidget(img_label)
            glayout.addWidget(QLabel(f"{w}x{h} px"))

        # Barcodes (para barcode steps: mostrar los nuevos)
        if snap.step.type == "barcode" and snap.barcodes:
            table = QTableWidget(len(snap.barcodes), 3)
            table.setHorizontalHeaderLabels(
                [self.tr("Valor"), self.tr("Simbologia"), self.tr("Calidad")]
            )
            table.setMaximumHeight(min(150, 30 + 25 * len(snap.barcodes)))
            for r, bc in enumerate(snap.barcodes):
                table.setItem(r, 0, QTableWidgetItem(bc.value))
                table.setItem(r, 1, QTableWidgetItem(bc.symbology))
                table.setItem(r, 2, QTableWidgetItem(f"{bc.quality:.2f}"))
            table.resizeColumnsToContents()
            glayout.addWidget(table)

        # OCR
        if snap.step.type == "ocr" and snap.ocr_text:
            text_edit = QPlainTextEdit(snap.ocr_text)
            text_edit.setReadOnly(True)
            text_edit.setMaximumHeight(120)
            glayout.addWidget(text_edit)

        # Fields (para script steps)
        if snap.step.type == "script" and snap.fields:
            table = QTableWidget(len(snap.fields), 2)
            table.setHorizontalHeaderLabels(
                [self.tr("Campo"), self.tr("Valor")]
            )
            table.setMaximumHeight(min(150, 30 + 25 * len(snap.fields)))
            for r, (k, v) in enumerate(snap.fields.items()):
                table.setItem(r, 0, QTableWidgetItem(str(k)))
                table.setItem(r, 1, QTableWidgetItem(str(v)))
            table.resizeColumnsToContents()
            glayout.addWidget(table)

        return group
