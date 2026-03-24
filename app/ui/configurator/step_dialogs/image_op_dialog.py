"""Diálogo de edición de paso ImageOp."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from app.pipeline.steps import ImageOpStep
from app.services.image_pipeline import IMAGE_OPS


class ImageOpDialog(QDialog):
    """Editor de paso de operación de imagen."""

    def __init__(
        self, step: ImageOpStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle(self.tr("Operación de imagen"))
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._op_combo = QComboBox()
        self._op_combo.addItems(sorted(IMAGE_OPS.keys()))
        if step.op:
            idx = self._op_combo.findText(step.op)
            if idx >= 0:
                self._op_combo.setCurrentIndex(idx)
        layout.addRow(self.tr("Operación:"), self._op_combo)

        # Parámetros como JSON simple clave=valor
        self._params_edit = QLineEdit()
        if step.params:
            self._params_edit.setText(
                ", ".join(f"{k}={v}" for k, v in step.params.items())
            )
        self._params_edit.setPlaceholderText("threshold=128, scale=0.5")
        layout.addRow(self.tr("Parámetros:"), self._params_edit)

        self._window_edit = QLineEdit()
        if step.window:
            self._window_edit.setText(
                ", ".join(str(v) for v in step.window)
            )
        self._window_edit.setPlaceholderText(self.tr("x, y, w, h (vacío = completa)"))
        layout.addRow(self.tr("Ventana:"), self._window_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> ImageOpStep:
        """Devuelve el paso con los valores editados."""
        self._step.op = self._op_combo.currentText()
        self._step.params = self._parse_params()
        self._step.window = self._parse_window()
        return self._step

    def _parse_params(self) -> dict:
        text = self._params_edit.text().strip()
        if not text:
            return {}
        params = {}
        for pair in text.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Intentar convertir a número
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                params[k] = v
        return params

    def _parse_window(self) -> tuple[int, int, int, int] | None:
        text = self._window_edit.text().strip()
        if not text:
            return None
        parts = [int(p.strip()) for p in text.split(",")]
        if len(parts) == 4:
            return tuple(parts)
        return None
