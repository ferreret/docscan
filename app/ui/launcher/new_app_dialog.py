"""Diálogo para crear una nueva aplicación."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QWidget,
)


class NewAppDialog(QDialog):
    """Diálogo simple para nombre y descripción de nueva aplicación."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Nueva aplicación"))
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(self.tr("Nombre único de la aplicación"))
        layout.addRow(self.tr("Nombre:"), self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText(self.tr("Descripción (opcional)"))
        self._desc_edit.setMaximumHeight(80)
        layout.addRow(self.tr("Descripción:"), self._desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self) -> None:
        if self._name_edit.text().strip():
            self.accept()

    def app_name(self) -> str:
        return self._name_edit.text().strip()

    def app_description(self) -> str:
        return self._desc_edit.toPlainText().strip()
