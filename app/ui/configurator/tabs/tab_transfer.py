"""Pestaña Transferencia del configurador."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from app.models.application import Application


class TransferTab(QWidget):
    """Configuración de transferencia de lotes."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        layout = QFormLayout(self)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["folder", "pdf", "pdfa", "csv", "script"])
        layout.addRow("Modo:", self._mode_combo)

        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("/ruta/destino/transferencia")
        layout.addRow("Destino:", self._dest_edit)

        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText(
            "{batch_id}_{page_index:04d}"
        )
        layout.addRow("Patrón nombre:", self._pattern_edit)

        self._subdirs = QCheckBox("Crear subdirectorios por lote")
        layout.addRow("", self._subdirs)

        self._pdf_dpi = QSpinBox()
        self._pdf_dpi.setRange(72, 600)
        self._pdf_dpi.setValue(200)
        layout.addRow("DPI (PDF):", self._pdf_dpi)

        self._csv_sep = QLineEdit(";")
        self._csv_sep.setMaximumWidth(50)
        layout.addRow("Separador CSV:", self._csv_sep)

        self._csv_fields_edit = QLineEdit()
        self._csv_fields_edit.setPlaceholderText("campo1, campo2 (vacío = auto)")
        layout.addRow("Campos CSV:", self._csv_fields_edit)

        self._metadata = QCheckBox("Incluir metadatos JSON")
        layout.addRow("", self._metadata)

    def _load_from_app(self, app: Application) -> None:
        try:
            config = json.loads(app.transfer_json) if app.transfer_json else {}
        except Exception:
            config = {}

        self._mode_combo.setCurrentText(config.get("mode", "folder"))
        self._dest_edit.setText(config.get("destination", ""))
        self._pattern_edit.setText(
            config.get("filename_pattern", "{batch_id}_{page_index:04d}")
        )
        self._subdirs.setChecked(config.get("create_subdirs", True))
        self._pdf_dpi.setValue(config.get("pdf_dpi", 200))
        self._csv_sep.setText(config.get("csv_separator", ";"))
        self._csv_fields_edit.setText(
            ", ".join(config.get("csv_fields", []))
        )
        self._metadata.setChecked(config.get("include_metadata", False))

    def apply_to(self, app: Application) -> None:
        csv_fields_text = self._csv_fields_edit.text().strip()
        csv_fields = [
            f.strip() for f in csv_fields_text.split(",") if f.strip()
        ] if csv_fields_text else []

        config = {
            "mode": self._mode_combo.currentText(),
            "destination": self._dest_edit.text().strip(),
            "filename_pattern": self._pattern_edit.text().strip(),
            "create_subdirs": self._subdirs.isChecked(),
            "pdf_dpi": self._pdf_dpi.value(),
            "csv_separator": self._csv_sep.text(),
            "csv_fields": csv_fields,
            "include_metadata": self._metadata.isChecked(),
        }
        app.transfer_json = json.dumps(config)
