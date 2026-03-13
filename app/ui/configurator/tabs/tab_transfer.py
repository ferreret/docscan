"""Pestaña Transferencia del configurador."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
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
        layout.setVerticalSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["folder", "pdf", "pdfa", "csv"])
        self._mode_combo.setToolTip(
            "folder = copia imágenes tal cual\n"
            "pdf = genera un PDF por lote\n"
            "pdfa = genera un PDF/A (archivable)\n"
            "csv = exporta índices a fichero CSV"
        )
        layout.addRow("Modo:", self._mode_combo)

        dest_row = QWidget()
        dest_layout = QHBoxLayout(dest_row)
        dest_layout.setContentsMargins(0, 0, 0, 0)
        dest_layout.setSpacing(4)
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("/ruta/destino/transferencia")
        self._dest_edit.setToolTip(
            "Carpeta donde se depositan los archivos transferidos"
        )
        dest_layout.addWidget(self._dest_edit)
        btn_browse = QPushButton("Examinar…")
        btn_browse.setFixedWidth(90)
        btn_browse.setToolTip("Seleccionar carpeta de destino")
        btn_browse.clicked.connect(self._browse_destination)
        dest_layout.addWidget(btn_browse)
        layout.addRow("Destino:", dest_row)

        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText(
            "{batch_id}_{page_index:04d}"
        )
        self._pattern_edit.setToolTip(
            "Plantilla para nombrar los archivos.\n"
            "Variables disponibles:\n"
            "  {batch_id} — ID del lote\n"
            "  {page_index} — Índice de página (base 0)\n"
            "  {first_barcode} — Valor del primer barcode detectado\n"
            "  {nombre_campo} — Campo de lote (espacios → guiones bajos)\n"
            "  :04d — Rellena con ceros (ej: 0001)\n"
            "  / — Crea subdirectorios\n\n"
            "Ejemplo: {fecha_lote}/{first_barcode}_{page_index:04d}"
        )
        layout.addRow("Patrón nombre:", self._pattern_edit)

        self._subdirs = QCheckBox("Crear subdirectorios por lote")
        self._subdirs.setToolTip(
            "Crea una subcarpeta por cada lote (ej: batch_123/)"
        )
        layout.addRow("", self._subdirs)

        self._pdf_dpi = QSpinBox()
        self._pdf_dpi.setRange(72, 600)
        self._pdf_dpi.setValue(200)
        self._pdf_dpi.setToolTip(
            "Resolución al generar PDF desde imágenes.\n"
            "Solo aplica a los modos pdf y pdfa."
        )
        layout.addRow("DPI (PDF):", self._pdf_dpi)

        self._csv_sep = QLineEdit(";")
        self._csv_sep.setMaximumWidth(50)
        self._csv_sep.setToolTip(
            "Carácter delimitador del fichero CSV.\n"
            "Solo aplica al modo csv."
        )
        layout.addRow("Separador CSV:", self._csv_sep)

        self._csv_fields_edit = QLineEdit()
        self._csv_fields_edit.setPlaceholderText("campo1, campo2 (vacío = auto)")
        self._csv_fields_edit.setToolTip(
            "Campos a exportar en el CSV, separados por coma.\n"
            "Vacío = exporta todos los campos automáticamente.\n"
            "Solo aplica al modo csv."
        )
        layout.addRow("Campos CSV:", self._csv_fields_edit)

        self._metadata = QCheckBox("Incluir metadatos JSON")
        self._metadata.setToolTip(
            "Genera un fichero .json junto a cada archivo\n"
            "con barcodes, texto OCR y campos de indexación."
        )
        layout.addRow("", self._metadata)

    def _browse_destination(self) -> None:
        """Abre diálogo para seleccionar carpeta de destino."""
        current = self._dest_edit.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de destino", current,
        )
        if folder:
            self._dest_edit.setText(folder)

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
