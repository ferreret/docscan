"""Splash screen de DocScan Studio.

Muestra logo, nombre, version y barra de progreso durante
la carga inicial de la aplicacion.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QVBoxLayout, QWidget


_SPLASH_W = 480
_SPLASH_H = 320
_VERSION = "3.0"


class SplashScreen(QSplashScreen):
    """Splash screen con logo, version y barra de progreso."""

    def __init__(self) -> None:
        pixmap = self._build_pixmap()
        super().__init__(pixmap)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
        )

        # Barra de progreso superpuesta
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setGeometry(0, _SPLASH_H - 4, _SPLASH_W, 4)
        self._progress.setStyleSheet(
            "QProgressBar { background: transparent; border: none; }"
            "QProgressBar::chunk { background: #89b4fa; border-radius: 2px; }"
        )

    def _build_pixmap(self) -> QPixmap:
        """Genera el pixmap del splash con QPainter."""
        pm = QPixmap(_SPLASH_W, _SPLASH_H)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Fondo degradado oscuro
        from PySide6.QtGui import QLinearGradient
        grad = QLinearGradient(0, 0, 0, _SPLASH_H)
        grad.setColorAt(0, QColor("#1e1e2e"))
        grad.setColorAt(1, QColor("#11111b"))
        p.fillRect(0, 0, _SPLASH_W, _SPLASH_H, grad)

        # Linea decorativa superior
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#89b4fa"))
        p.drawRect(0, 0, _SPLASH_W, 3)

        # Logo SVG si existe
        icon_path = Path(__file__).parent.parent.parent / "resources" / "icons" / "docscan.svg"
        if icon_path.exists():
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtCore import QRectF
            renderer = QSvgRenderer(str(icon_path))
            logo_size = 80
            logo_x = (_SPLASH_W - logo_size) / 2
            logo_y = 40
            renderer.render(p, QRectF(logo_x, logo_y, logo_size, logo_size))
            text_y = 135
        else:
            text_y = 80

        # Titulo
        p.setPen(QColor("#cdd6f4"))
        font_title = QFont("Segoe UI", 28)
        font_title.setWeight(QFont.Weight.Bold)
        p.setFont(font_title)
        p.drawText(0, text_y, _SPLASH_W, 45, Qt.AlignmentFlag.AlignCenter, "DocScan Studio")

        # Version
        p.setPen(QColor("#6c7086"))
        font_ver = QFont("Segoe UI", 12)
        p.setFont(font_ver)
        p.drawText(0, text_y + 42, _SPLASH_W, 25, Qt.AlignmentFlag.AlignCenter, f"v{_VERSION}")

        # Subtitulo
        p.setPen(QColor("#585b70"))
        font_sub = QFont("Segoe UI", 10)
        p.setFont(font_sub)
        p.drawText(
            0, text_y + 70, _SPLASH_W, 25,
            Qt.AlignmentFlag.AlignCenter,
            "Document Scanning & Processing",
        )

        # Copyright
        p.setPen(QColor("#45475a"))
        font_copy = QFont("Segoe UI", 8)
        p.setFont(font_copy)
        p.drawText(
            0, _SPLASH_H - 30, _SPLASH_W, 20,
            Qt.AlignmentFlag.AlignCenter,
            "Tecnomedia  2026",
        )

        p.end()
        return pm

    def set_progress(self, value: int) -> None:
        """Actualiza la barra de progreso (0-100)."""
        self._progress.setValue(value)

    def set_status(self, text: str) -> None:
        """Muestra un mensaje de estado en el splash."""
        self.showMessage(
            text,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#6c7086"),
        )
