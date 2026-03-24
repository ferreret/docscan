"""Pestaña Imagen del configurador de aplicación."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.models.image_config import ImageConfig, parse_image_config, serialize_image_config


class ImageTab(QWidget):
    """Configuración de formato de imagen (escáner)."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_from(app)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- Grupo: Formato interno (escáner) ---
        group = QGroupBox(self.tr("Formato interno (escáner)"))
        form = QFormLayout(group)
        form.setVerticalSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["tiff", "png", "jpg"])
        self._format_combo.setToolTip(
            self.tr("Formato en el que se almacenan las imágenes del escáner")
        )
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        form.addRow(self.tr("Formato:"), self._format_combo)

        self._color_combo = QComboBox()
        self._color_combo.addItems(["color", "grayscale", "bw"])
        self._color_combo.setToolTip(
            self.tr(
                "Conversión de color al almacenar (solo reduce, no añade color).\n"
                "color = sin conversión (se guarda tal como llega del escáner)\n"
                "grayscale = convierte a escala de grises\n"
                "bw = convierte a blanco y negro (umbralización)"
            )
        )
        self._color_combo.currentTextChanged.connect(self._on_color_changed)
        form.addRow(self.tr("Modo color:"), self._color_combo)

        # Compresión TIFF
        self._tiff_comp_combo = QComboBox()
        self._tiff_comp_combo.addItems(["lzw", "zip", "none", "group4"])
        self._tiff_comp_combo.setToolTip(
            self.tr(
                "Tipo de compresión para ficheros TIFF.\n"
                "group4 solo funciona con imágenes B/N."
            )
        )
        self._tiff_comp_label = QLabel(self.tr("Compresión:"))
        form.addRow(self._tiff_comp_label, self._tiff_comp_combo)

        # Calidad JPEG
        self._jpeg_quality_spin = QSpinBox()
        self._jpeg_quality_spin.setRange(1, 100)
        self._jpeg_quality_spin.setValue(85)
        self._jpeg_quality_spin.setToolTip(self.tr("Calidad JPEG (1=mínima, 100=máxima)"))
        self._jpeg_quality_label = QLabel(self.tr("Calidad JPEG:"))
        form.addRow(self._jpeg_quality_label, self._jpeg_quality_spin)

        # Compresión PNG
        self._png_comp_spin = QSpinBox()
        self._png_comp_spin.setRange(0, 9)
        self._png_comp_spin.setValue(6)
        self._png_comp_spin.setToolTip(self.tr("Nivel de compresión PNG (0=sin, 9=máxima)"))
        self._png_comp_label = QLabel(self.tr("Compresión PNG:"))
        form.addRow(self._png_comp_label, self._png_comp_spin)

        # Umbral B/N
        self._bw_threshold_spin = QSpinBox()
        self._bw_threshold_spin.setRange(0, 255)
        self._bw_threshold_spin.setValue(128)
        self._bw_threshold_spin.setToolTip(
            self.tr("Umbral para binarización blanco/negro (0-255)")
        )
        self._bw_threshold_label = QLabel(self.tr("Umbral B/N:"))
        form.addRow(self._bw_threshold_label, self._bw_threshold_spin)

        main_layout.addWidget(group)

        # Nota informativa
        note = QLabel(
            self.tr(
                "Nota: Los archivos importados se almacenan en su formato original.\n"
                "El modo color solo puede reducir (color→gris→B/N), no añadir color."
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(note)

        main_layout.addStretch()

        # Estado inicial de visibilidad
        self._on_format_changed(self._format_combo.currentText())
        self._on_color_changed(self._color_combo.currentText())

    def _on_format_changed(self, fmt: str) -> None:
        """Muestra/oculta controles según el formato seleccionado."""
        is_tiff = fmt == "tiff"
        is_jpg = fmt == "jpg"
        is_png = fmt == "png"

        self._tiff_comp_label.setVisible(is_tiff)
        self._tiff_comp_combo.setVisible(is_tiff)
        self._jpeg_quality_label.setVisible(is_jpg)
        self._jpeg_quality_spin.setVisible(is_jpg)
        self._png_comp_label.setVisible(is_png)
        self._png_comp_spin.setVisible(is_png)

    def _on_color_changed(self, mode: str) -> None:
        """Muestra/oculta umbral B/N."""
        is_bw = mode == "bw"
        self._bw_threshold_label.setVisible(is_bw)
        self._bw_threshold_spin.setVisible(is_bw)

    def _load_from(self, app: Application) -> None:
        """Carga configuración desde la aplicación."""
        config = parse_image_config(
            getattr(app, "image_config_json", "{}") or "{}"
        )

        idx = self._format_combo.findText(config.format)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
        idx = self._color_combo.findText(config.color_mode)
        if idx >= 0:
            self._color_combo.setCurrentIndex(idx)
        self._jpeg_quality_spin.setValue(config.jpeg_quality)
        idx = self._tiff_comp_combo.findText(config.tiff_compression)
        if idx >= 0:
            self._tiff_comp_combo.setCurrentIndex(idx)
        self._png_comp_spin.setValue(config.png_compression)
        self._bw_threshold_spin.setValue(config.bw_threshold)

    def apply_to(self, app: Application) -> None:
        """Aplica los valores del formulario al objeto Application."""
        config = ImageConfig(
            format=self._format_combo.currentText(),
            color_mode=self._color_combo.currentText(),
            jpeg_quality=self._jpeg_quality_spin.value(),
            tiff_compression=self._tiff_comp_combo.currentText(),
            png_compression=self._png_comp_spin.value(),
            bw_threshold=self._bw_threshold_spin.value(),
        )
        app.image_config_json = serialize_image_config(config)
        # Sincronizar output_format para retrocompatibilidad
        app.output_format = config.format
