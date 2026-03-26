"""Diálogo «Acerca de» de DocScan Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app._version import __version__ as _VERSION
_APP_NAME = "DocScan Studio"
_COPYRIGHT = "© 2026 Tecnomedia"
_DESCRIPTION = (
    "Plataforma de captura, procesamiento e indexación de documentos "
    "con pipeline composable e IA generativa."
)

_STACK_ITEMS = [
    "Python 3.14", "PySide6", "SQLAlchemy 2", "OpenCV",
    "PyMuPDF", "RapidOCR", "pyzbar", "zxing-cpp",
    "Anthropic SDK", "OpenAI SDK",
]


class AboutDialog(QDialog):
    """Ventana modal con información de la aplicación."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Acerca de {0}").format(_APP_NAME))
        self.setFixedSize(480, 380)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Cabecera: icono + nombre + versión
        header = QHBoxLayout()
        header.setSpacing(16)

        icon_label = QLabel()
        icon_label.setFixedSize(64, 64)
        try:
            from pathlib import Path
            icon_path = Path(__file__).parent.parent.parent / "resources" / "icons" / "docscan.svg"
            if icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                icon_label.setPixmap(
                    pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                )
        except Exception:
            pass
        header.addWidget(icon_label)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        name_label = QLabel(_APP_NAME)
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        name_label.setFont(name_font)
        title_block.addWidget(name_label)

        version_label = QLabel(self.tr("Versión {0}").format(_VERSION))
        version_font = QFont()
        version_font.setPointSize(11)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #888;")
        title_block.addWidget(version_label)

        title_block.addStretch()
        header.addLayout(title_block)
        header.addStretch()
        layout.addLayout(header)

        # Separador
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #444;")
        layout.addWidget(sep)

        # Descripción
        desc_label = QLabel(_DESCRIPTION)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(desc_label)

        # Stack tecnológico
        stack_label = QLabel(self.tr("Stack tecnológico:"))
        stack_font = QFont()
        stack_font.setBold(True)
        stack_label.setFont(stack_font)
        layout.addWidget(stack_label)

        stack_text = QLabel("  •  ".join(_STACK_ITEMS))
        stack_text.setWordWrap(True)
        stack_text.setStyleSheet("color: #aaa; font-size: 10pt;")
        layout.addWidget(stack_text)

        layout.addStretch()

        # Copyright + botón cerrar
        footer = QHBoxLayout()
        copyright_label = QLabel(_COPYRIGHT)
        copyright_label.setStyleSheet("color: #888; font-size: 10pt;")
        footer.addWidget(copyright_label)
        footer.addStretch()

        btn_close = QPushButton(self.tr("Cerrar"))
        btn_close.setFixedWidth(90)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)
