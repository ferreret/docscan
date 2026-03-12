"""Fábrica de iconos vectoriales para la toolbar.

Genera QIcon a partir de QPainter para que escalen bien
en cualquier resolución y se adapten al tema activo.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


def _new_pixmap(size: int = 32) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def icon_sun(color: str = "#f9e2af", size: int = 32) -> QIcon:
    """Icono de sol (tema claro)."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)

    cx, cy = size // 2, size // 2
    r = size // 5

    # Círculo central
    p.drawEllipse(QPoint(cx, cy), r, r)

    # Rayos
    pen = QPen(c, max(1, size // 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    import math
    ray_inner = r + max(2, size // 10)
    ray_outer = int(size * 0.42)
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + int(ray_inner * math.cos(angle))
        y1 = cy + int(ray_inner * math.sin(angle))
        x2 = cx + int(ray_outer * math.cos(angle))
        y2 = cy + int(ray_outer * math.sin(angle))
        p.drawLine(x1, y1, x2, y2)

    p.end()
    return QIcon(pm)


def icon_moon(color: str = "#89b4fa", size: int = 32) -> QIcon:
    """Icono de luna (tema oscuro)."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)

    # Luna creciente: círculo grande - círculo recortado
    r = int(size * 0.35)
    cx, cy = size // 2, size // 2
    p.drawEllipse(QPoint(cx - 1, cy), r, r)

    # Recortar con el fondo (transparente)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    offset = int(size * 0.22)
    p.drawEllipse(QPoint(cx + offset, cy - offset // 2), r, r)

    p.end()
    return QIcon(pm)


def icon_font_increase(color: str = "#cdd6f4", size: int = 32) -> QIcon:
    """Icono A+ para aumentar fuente."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    c = QColor(color)

    # Letra "A" grande
    font_a = QFont("Segoe UI", int(size * 0.42))
    font_a.setWeight(QFont.Weight.Bold)
    p.setFont(font_a)
    p.setPen(c)
    a_rect = QRect(0, 0, int(size * 0.65), size)
    p.drawText(a_rect, Qt.AlignmentFlag.AlignCenter, "A")

    # Signo "+" pequeño
    pen = QPen(c, max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    plus_cx = int(size * 0.78)
    plus_cy = int(size * 0.35)
    arm = int(size * 0.13)
    p.drawLine(plus_cx - arm, plus_cy, plus_cx + arm, plus_cy)
    p.drawLine(plus_cx, plus_cy - arm, plus_cx, plus_cy + arm)

    p.end()
    return QIcon(pm)


def icon_font_decrease(color: str = "#cdd6f4", size: int = 32) -> QIcon:
    """Icono A- para reducir fuente."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    c = QColor(color)

    # Letra "A" grande
    font_a = QFont("Segoe UI", int(size * 0.42))
    font_a.setWeight(QFont.Weight.Bold)
    p.setFont(font_a)
    p.setPen(c)
    a_rect = QRect(0, 0, int(size * 0.65), size)
    p.drawText(a_rect, Qt.AlignmentFlag.AlignCenter, "A")

    # Signo "−" pequeño
    pen = QPen(c, max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    minus_cx = int(size * 0.78)
    minus_cy = int(size * 0.35)
    arm = int(size * 0.13)
    p.drawLine(minus_cx - arm, minus_cy, minus_cx + arm, minus_cy)

    p.end()
    return QIcon(pm)
