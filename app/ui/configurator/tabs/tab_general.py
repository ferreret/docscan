"""Pestaña General del configurador de aplicación."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QWidget,
)

from app.models.application import Application


class GeneralTab(QWidget):
    """Pestaña de configuración general de la aplicación."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui(app)

    def _setup_ui(self, app: Application) -> None:
        layout = QFormLayout(self)

        self._name_edit = QLineEdit(app.name)
        layout.addRow("Nombre:", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(app.description)
        self._desc_edit.setMaximumHeight(80)
        layout.addRow("Descripción:", self._desc_edit)

        self._active_check = QCheckBox("Activa")
        self._active_check.setChecked(app.active)
        layout.addRow("", self._active_check)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["tiff", "png", "jpg", "bmp"])
        idx = self._format_combo.findText(app.output_format)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
        layout.addRow("Formato de salida:", self._format_combo)

        self._scanner_combo = QComboBox()
        self._scanner_combo.addItems(["sane", "twain", "wia"])
        idx = self._scanner_combo.findText(app.scanner_backend)
        if idx >= 0:
            self._scanner_combo.setCurrentIndex(idx)
        layout.addRow("Backend escáner:", self._scanner_combo)

        self._auto_transfer = QCheckBox("Transferir automáticamente")
        self._auto_transfer.setChecked(app.auto_transfer)
        layout.addRow("", self._auto_transfer)

        self._close_after = QCheckBox("Cerrar tras transferir")
        self._close_after.setChecked(app.close_after_transfer)
        layout.addRow("", self._close_after)

    def apply_to(self, app: Application) -> None:
        """Aplica los valores del formulario al objeto Application."""
        app.name = self._name_edit.text().strip()
        app.description = self._desc_edit.toPlainText().strip()
        app.active = self._active_check.isChecked()
        app.output_format = self._format_combo.currentText()
        app.scanner_backend = self._scanner_combo.currentText()
        app.auto_transfer = self._auto_transfer.isChecked()
        app.close_after_transfer = self._close_after.isChecked()
