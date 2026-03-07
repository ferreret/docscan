"""Diálogo de edición de paso HTTP Request."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from app.pipeline.steps import HttpRequestStep


class HttpRequestDialog(QDialog):
    """Editor de paso de petición HTTP."""

    def __init__(
        self, step: HttpRequestStep, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle("Petición HTTP")
        self.setMinimumWidth(500)

        layout = QFormLayout(self)

        self._label_edit = QLineEdit(step.label)
        self._label_edit.setPlaceholderText("Nombre descriptivo")
        layout.addRow("Etiqueta:", self._label_edit)

        self._method_combo = QComboBox()
        self._method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE"])
        self._method_combo.setCurrentText(step.method)
        layout.addRow("Método:", self._method_combo)

        self._url_edit = QLineEdit(step.url)
        self._url_edit.setPlaceholderText(
            "https://api.example.com/endpoint"
        )
        layout.addRow("URL:", self._url_edit)

        self._headers_edit = QLineEdit()
        if step.headers:
            self._headers_edit.setText(
                ", ".join(f"{k}: {v}" for k, v in step.headers.items())
            )
        self._headers_edit.setPlaceholderText(
            "Authorization: Bearer xxx, Content-Type: application/json"
        )
        layout.addRow("Headers:", self._headers_edit)

        self._body_edit = QPlainTextEdit()
        self._body_edit.setPlainText(step.body)
        self._body_edit.setMaximumHeight(100)
        self._body_edit.setPlaceholderText('{"barcode": "{page.barcodes[0].value}"}')
        layout.addRow("Body:", self._body_edit)

        self._on_error_combo = QComboBox()
        self._on_error_combo.addItems(["continue", "abort"])
        self._on_error_combo.setCurrentText(step.on_error)
        layout.addRow("Si error:", self._on_error_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_step(self) -> HttpRequestStep:
        self._step.label = self._label_edit.text().strip()
        self._step.method = self._method_combo.currentText()
        self._step.url = self._url_edit.text().strip()
        self._step.headers = self._parse_headers()
        self._step.body = self._body_edit.toPlainText()
        self._step.on_error = self._on_error_combo.currentText()
        return self._step

    def _parse_headers(self) -> dict[str, str]:
        text = self._headers_edit.text().strip()
        if not text:
            return {}
        headers = {}
        for pair in text.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers
