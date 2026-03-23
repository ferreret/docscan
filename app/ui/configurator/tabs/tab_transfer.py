"""Pestaña Transferencia del configurador."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application

_SENTINEL_ORIGINAL = "(original)"


class TransferTab(QWidget):
    """Configuración de transferencia de lotes."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_from_app(app)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ── Grupo: Configuración general ──
        general_group = QGroupBox("Configuración general")
        gen_form = QFormLayout(general_group)
        gen_form.setVerticalSpacing(8)
        gen_form.setContentsMargins(12, 12, 12, 12)

        self._enabled_check = QCheckBox("Habilitar transferencia estándar")
        self._enabled_check.setToolTip(
            "Si está desmarcado, solo se ejecutará el evento\n"
            "on_transfer_advanced (si está definido).\n"
            "Útil cuando la transferencia se gestiona íntegramente por script."
        )
        self._enabled_check.setChecked(True)
        self._enabled_check.toggled.connect(self._on_enabled_changed)
        gen_form.addRow("", self._enabled_check)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["folder", "pdf", "pdfa", "csv"])
        self._mode_combo.setToolTip(
            "folder = copia imágenes a carpeta destino\n"
            "pdf = genera un PDF por lote\n"
            "pdfa = genera un PDF/A (archivable)\n"
            "csv = exporta índices a fichero CSV"
        )
        gen_form.addRow("Modo:", self._mode_combo)

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
        gen_form.addRow("Destino:", dest_row)

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
        gen_form.addRow("Patrón nombre:", self._pattern_edit)

        self._subdirs = QCheckBox("Crear subdirectorios por lote")
        self._subdirs.setToolTip(
            "Crea una subcarpeta por cada lote (ej: batch_123/)"
        )
        gen_form.addRow("", self._subdirs)

        self._metadata = QCheckBox("Incluir metadatos JSON")
        self._metadata.setToolTip(
            "Genera un fichero .json junto a cada archivo\n"
            "con barcodes, texto OCR y campos de indexación."
        )
        gen_form.addRow("", self._metadata)

        main_layout.addWidget(general_group)

        # ── Grupo: Formato de salida (solo modo carpeta) ──
        self._output_group = QGroupBox(
            "Conversión al transferir (modo carpeta)"
        )
        out_form = QFormLayout(self._output_group)
        out_form.setVerticalSpacing(8)
        out_form.setContentsMargins(12, 12, 12, 12)

        out_hint = QLabel(
            "Convierte las imágenes al copiarlas a la carpeta destino.\n"
            "Selecciona (original) para copiar sin modificar."
        )
        out_hint.setObjectName("hint_label")
        out_hint.setWordWrap(True)
        out_form.addRow(out_hint)

        self._out_format_combo = QComboBox()
        self._out_format_combo.addItems([_SENTINEL_ORIGINAL, "tiff", "png", "jpg"])
        self._out_format_combo.setToolTip(
            "(original) = se mantiene el formato almacenado\n"
            "Seleccionar otro formato convierte al transferir"
        )
        self._out_format_combo.currentTextChanged.connect(
            self._on_out_format_changed
        )
        out_form.addRow("Formato:", self._out_format_combo)

        self._out_dpi_spin = QSpinBox()
        self._out_dpi_spin.setRange(0, 1200)
        self._out_dpi_spin.setValue(0)
        self._out_dpi_spin.setSpecialValueText(_SENTINEL_ORIGINAL)
        self._out_dpi_spin.setSuffix(" DPI")
        self._out_dpi_spin.setToolTip(
            "0 = mantener resolución original\n"
            "Otro valor redimensiona la imagen proporcionalmente"
        )
        out_form.addRow("DPI:", self._out_dpi_spin)

        self._out_color_combo = QComboBox()
        self._out_color_combo.addItems(
            [_SENTINEL_ORIGINAL, "grayscale", "bw"]
        )
        self._out_color_combo.setToolTip(
            "(original) = sin conversión de color\n"
            "grayscale = escala de grises\n"
            "bw = blanco y negro (binario)"
        )
        out_form.addRow("Color:", self._out_color_combo)

        color_hint = QLabel(
            "Solo reduce: color → gris → B/N. "
            "No es posible recuperar color a partir de gris o B/N."
        )
        color_hint.setObjectName("hint_label")
        color_hint.setWordWrap(True)
        out_form.addRow(color_hint)

        self._out_quality_spin = QSpinBox()
        self._out_quality_spin.setRange(1, 100)
        self._out_quality_spin.setValue(85)
        self._out_quality_spin.setToolTip("Calidad JPEG de salida (1-100)")
        self._out_quality_label = QLabel("Calidad JPEG:")
        out_form.addRow(self._out_quality_label, self._out_quality_spin)

        self._out_tiff_comp = QComboBox()
        self._out_tiff_comp.addItems(["lzw", "zip", "none", "group4"])
        self._out_tiff_comp_label = QLabel("Compresión TIFF:")
        out_form.addRow(self._out_tiff_comp_label, self._out_tiff_comp)

        self._out_png_comp = QSpinBox()
        self._out_png_comp.setRange(0, 9)
        self._out_png_comp.setValue(6)
        self._out_png_comp_label = QLabel("Compresión PNG:")
        out_form.addRow(self._out_png_comp_label, self._out_png_comp)

        main_layout.addWidget(self._output_group)

        # ── Grupo: Opciones PDF (solo modos pdf/pdfa) ──
        self._pdf_group = QGroupBox("Opciones PDF")
        pdf_form = QFormLayout(self._pdf_group)
        pdf_form.setVerticalSpacing(8)
        pdf_form.setContentsMargins(12, 12, 12, 12)

        self._pdf_dpi = QSpinBox()
        self._pdf_dpi.setRange(72, 600)
        self._pdf_dpi.setValue(200)
        self._pdf_dpi.setSuffix(" DPI")
        self._pdf_dpi.setToolTip(
            "Resolución al generar páginas PDF desde imágenes"
        )
        pdf_form.addRow("DPI del PDF:", self._pdf_dpi)

        self._pdf_jpeg_quality_spin = QSpinBox()
        self._pdf_jpeg_quality_spin.setRange(1, 100)
        self._pdf_jpeg_quality_spin.setValue(85)
        self._pdf_jpeg_quality_spin.setToolTip(
            "Calidad JPEG al codificar imágenes dentro del PDF (1-100)\n"
            "Menor = fichero más pequeño, peor calidad"
        )
        pdf_form.addRow("Calidad JPEG:", self._pdf_jpeg_quality_spin)

        main_layout.addWidget(self._pdf_group)

        # ── Grupo: Opciones CSV (solo modo csv) ──
        self._csv_group = QGroupBox("Opciones CSV")
        csv_form = QFormLayout(self._csv_group)
        csv_form.setVerticalSpacing(8)
        csv_form.setContentsMargins(12, 12, 12, 12)

        self._csv_sep = QLineEdit(";")
        self._csv_sep.setMaximumWidth(50)
        self._csv_sep.setToolTip("Carácter delimitador del fichero CSV")
        csv_form.addRow("Separador:", self._csv_sep)

        self._csv_fields_edit = QLineEdit()
        self._csv_fields_edit.setPlaceholderText(
            "campo1, campo2 (vacío = auto)"
        )
        self._csv_fields_edit.setToolTip(
            "Campos a exportar en el CSV, separados por coma.\n"
            "Vacío = exporta todos los campos automáticamente."
        )
        csv_form.addRow("Campos:", self._csv_fields_edit)

        main_layout.addWidget(self._csv_group)

        main_layout.addStretch()

        # Conectar visibilidad según modo
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(self._mode_combo.currentText())
        self._on_out_format_changed(self._out_format_combo.currentText())

    def _on_enabled_changed(self, enabled: bool) -> None:
        """Habilita/deshabilita los controles de transferencia estándar."""
        self._mode_combo.setEnabled(enabled)
        self._dest_edit.setEnabled(enabled)
        self._pattern_edit.setEnabled(enabled)
        self._subdirs.setEnabled(enabled)
        self._metadata.setEnabled(enabled)
        self._output_group.setEnabled(enabled)
        self._pdf_group.setEnabled(enabled)
        self._csv_group.setEnabled(enabled)

    def _on_mode_changed(self, mode: str) -> None:
        """Muestra/oculta grupos según el modo de transferencia."""
        is_folder = mode == "folder"
        is_pdf = mode in ("pdf", "pdfa")
        is_csv = mode == "csv"
        self._output_group.setVisible(is_folder)
        self._pdf_group.setVisible(is_pdf)
        self._csv_group.setVisible(is_csv)

    def _on_out_format_changed(self, fmt: str) -> None:
        """Muestra/oculta opciones de formato de salida."""
        is_jpg = fmt == "jpg"
        is_tiff = fmt == "tiff"
        is_png = fmt == "png"
        self._out_quality_label.setVisible(is_jpg)
        self._out_quality_spin.setVisible(is_jpg)
        self._out_tiff_comp_label.setVisible(is_tiff)
        self._out_tiff_comp.setVisible(is_tiff)
        self._out_png_comp_label.setVisible(is_png)
        self._out_png_comp.setVisible(is_png)

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

        self._enabled_check.setChecked(config.get("standard_enabled", True))
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

        # Formato de salida
        out_fmt = config.get("output_format", "")
        if out_fmt:
            idx = self._out_format_combo.findText(out_fmt)
            if idx >= 0:
                self._out_format_combo.setCurrentIndex(idx)
        else:
            self._out_format_combo.setCurrentIndex(0)  # (original)

        self._out_dpi_spin.setValue(config.get("output_dpi", 0))

        out_color = config.get("output_color_mode", "")
        if out_color:
            idx = self._out_color_combo.findText(out_color)
            if idx >= 0:
                self._out_color_combo.setCurrentIndex(idx)
        else:
            self._out_color_combo.setCurrentIndex(0)  # (original)

        self._out_quality_spin.setValue(config.get("output_jpeg_quality", 85))
        self._out_tiff_comp.setCurrentText(
            config.get("output_tiff_compression", "lzw")
        )
        self._out_png_comp.setValue(config.get("output_png_compression", 6))
        self._pdf_jpeg_quality_spin.setValue(
            config.get("pdf_jpeg_quality", 85)
        )

    def apply_to(self, app: Application) -> None:
        csv_fields_text = self._csv_fields_edit.text().strip()
        csv_fields = [
            f.strip() for f in csv_fields_text.split(",") if f.strip()
        ] if csv_fields_text else []

        # Formato de salida
        out_fmt = self._out_format_combo.currentText()
        output_format = "" if out_fmt == _SENTINEL_ORIGINAL else out_fmt
        out_color = self._out_color_combo.currentText()
        output_color_mode = "" if out_color == _SENTINEL_ORIGINAL else out_color

        config = {
            "standard_enabled": self._enabled_check.isChecked(),
            "mode": self._mode_combo.currentText(),
            "destination": self._dest_edit.text().strip(),
            "filename_pattern": self._pattern_edit.text().strip(),
            "create_subdirs": self._subdirs.isChecked(),
            "pdf_dpi": self._pdf_dpi.value(),
            "csv_separator": self._csv_sep.text(),
            "csv_fields": csv_fields,
            "include_metadata": self._metadata.isChecked(),
            "output_format": output_format,
            "output_dpi": self._out_dpi_spin.value(),
            "output_color_mode": output_color_mode,
            "output_jpeg_quality": self._out_quality_spin.value(),
            "output_tiff_compression": self._out_tiff_comp.currentText(),
            "output_png_compression": self._out_png_comp.value(),
            "pdf_jpeg_quality": self._pdf_jpeg_quality_spin.value(),
        }
        app.transfer_json = json.dumps(config)
