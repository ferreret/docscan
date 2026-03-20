"""Barra de herramientas flotante sobre el visor de documentos.

Contiene navegación, zoom y herramientas de manipulación como overlay
semitransparente en la parte inferior del visor.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

log = logging.getLogger(__name__)

_SZ = 32  # Tamaño base de los iconos


def _pm() -> QPixmap:
    pm = QPixmap(_SZ, _SZ)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _pen(color: str = "#cdd6f4", width: float = 2.0) -> QPen:
    p = QPen(QColor(color), width)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


# -- Iconos de navegación --

def _icon_first(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 3.0))
    p.drawLine(7, 8, 7, 24)
    p.drawLine(19, 8, 11, 16)
    p.drawLine(11, 16, 19, 24)
    p.drawLine(27, 8, 19, 16)
    p.drawLine(19, 16, 27, 24)
    p.end()
    return QIcon(pm)


def _icon_prev(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 3.0))
    p.drawLine(21, 7, 11, 16)
    p.drawLine(11, 16, 21, 25)
    p.end()
    return QIcon(pm)


def _icon_next(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 3.0))
    p.drawLine(11, 7, 21, 16)
    p.drawLine(21, 16, 11, 25)
    p.end()
    return QIcon(pm)


def _icon_last(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 3.0))
    p.drawLine(5, 8, 13, 16)
    p.drawLine(13, 16, 5, 24)
    p.drawLine(13, 8, 21, 16)
    p.drawLine(21, 16, 13, 24)
    p.drawLine(25, 8, 25, 24)
    p.end()
    return QIcon(pm)


def _icon_nav_script(color: str = "#cdd6f4") -> QIcon:
    """Flecha + engranaje: navegación programable."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Flecha derecha pequeña
    p.setPen(_pen(color, 2.5))
    p.drawLine(4, 10, 12, 16)
    p.drawLine(12, 16, 4, 22)
    # Engranaje simplificado (círculo con muescas)
    p.setPen(_pen(color, 2.0))
    p.drawEllipse(QPoint(22, 16), 5, 5)
    for angle_offset in range(0, 360, 60):
        import math
        rad = math.radians(angle_offset)
        x1 = 22 + int(6 * math.cos(rad))
        y1 = 16 + int(6 * math.sin(rad))
        x2 = 22 + int(8 * math.cos(rad))
        y2 = 16 + int(8 * math.sin(rad))
        p.drawLine(x1, y1, x2, y2)
    p.end()
    return QIcon(pm)


def _icon_next_barcode(color: str = "#cdd6f4") -> QIcon:
    """Flecha + líneas verticales: siguiente con barcode."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    # Flecha derecha
    p.drawLine(4, 10, 12, 16)
    p.drawLine(12, 16, 4, 22)
    # Barcode simplificado (líneas verticales)
    p.setPen(_pen(color, 2.0))
    for x in (18, 21, 23, 26, 28):
        p.drawLine(x, 9, x, 23)
    p.end()
    return QIcon(pm)


def _icon_next_review(color: str = "#cdd6f4") -> QIcon:
    """Flecha + signo de exclamación: siguiente pendiente de revisión."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    # Flecha derecha
    p.drawLine(4, 10, 12, 16)
    p.drawLine(12, 16, 4, 22)
    # Exclamación
    p.setPen(_pen("#e53935", 3.0))
    p.drawLine(24, 8, 24, 18)
    p.drawPoint(24, 23)
    p.end()
    return QIcon(pm)


# -- Iconos de zoom --

def _icon_zoom_in(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawEllipse(QPoint(13, 13), 9, 9)
    p.drawLine(20, 20, 28, 28)
    p.drawLine(9, 13, 17, 13)
    p.drawLine(13, 9, 13, 17)
    p.end()
    return QIcon(pm)


def _icon_zoom_out(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawEllipse(QPoint(13, 13), 9, 9)
    p.drawLine(20, 20, 28, 28)
    p.drawLine(9, 13, 17, 13)
    p.end()
    return QIcon(pm)


def _icon_zoom_fit(color: str = "#cdd6f4") -> QIcon:
    """Ajustar a página: 4 flechas hacia dentro."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawRect(9, 9, 14, 14)
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        cx = 16 + dx * 11
        cy = 16 + dy * 11
        tx = 16 + dx * 7
        ty = 16 + dy * 7
        p.drawLine(cx, cy, tx, ty)
    p.end()
    return QIcon(pm)


def _icon_zoom_100(color: str = "#cdd6f4") -> QIcon:
    """1:1 como texto."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont("Segoe UI", 12)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRect(0, 0, _SZ, _SZ), Qt.AlignmentFlag.AlignCenter, "1:1")
    p.end()
    return QIcon(pm)


# -- Iconos de herramientas --

def _icon_rotate(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawArc(5, 5, 22, 22, 30 * 16, 300 * 16)
    p.drawLine(24, 7, 27, 13)
    p.drawLine(24, 7, 19, 8)
    p.end()
    return QIcon(pm)


def _icon_mark(color: str = "#cdd6f4") -> QIcon:
    """Bandera para marcar/excluir."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawLine(8, 5, 8, 27)
    p.setPen(_pen("#fb8c00", 2.5))
    p.setBrush(QColor("#fb8c00"))
    pts = [QPoint(9, 6), QPoint(25, 12), QPoint(9, 17)]
    p.drawPolygon(pts)
    p.end()
    return QIcon(pm)


def _icon_delete_current(color: str = "#e53935") -> QIcon:
    """X para eliminar página actual."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 3.0))
    p.drawLine(8, 8, 24, 24)
    p.drawLine(24, 8, 8, 24)
    p.end()
    return QIcon(pm)


def _icon_delete_from(color: str = "#e53935") -> QIcon:
    """Tijeras para borrar desde aquí."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawEllipse(QPoint(9, 23), 5, 5)
    p.drawEllipse(QPoint(23, 23), 5, 5)
    p.drawLine(12, 19, 23, 5)
    p.drawLine(20, 19, 9, 5)
    p.end()
    return QIcon(pm)


def _make_button(
    icon: QIcon,
    tooltip: str,
    *,
    width: int = 38,
    obj_name: str = "",
) -> QPushButton:
    """Crea un botón con icono pintado para el overlay."""
    btn = QPushButton()
    btn.setIcon(icon)
    btn.setIconSize(btn.iconSize().expandedTo(QPixmap(_SZ, _SZ).size()))
    btn.setToolTip(tooltip)
    btn.setFixedSize(width, 36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if obj_name:
        btn.setObjectName(obj_name)
    return btn


class ViewerOverlay(QWidget):
    """Barra flotante de herramientas sobre el visor.

    Signals:
        nav_first, nav_prev, nav_next, nav_last: Navegación básica.
        nav_script: Navegación programable por script.
        zoom_in, zoom_out, zoom_fit, zoom_100: Control de zoom.
        rotate_requested: Rotar 90°.
        mark_requested: Marcar/desmarcar página.
        delete_current_requested: Eliminar página actual.
        delete_from_requested: Borrar desde página actual.
    """

    # Navegación
    nav_first = Signal()
    nav_prev = Signal()
    nav_next = Signal()
    nav_last = Signal()
    nav_next_barcode = Signal()
    nav_next_review = Signal()
    nav_script = Signal()

    # Zoom
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    zoom_fit_requested = Signal()
    zoom_100_requested = Signal()

    # Herramientas
    rotate_requested = Signal()
    mark_requested = Signal()
    delete_current_requested = Signal()
    delete_from_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewerOverlay")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        c = "#cdd6f4"  # Color base (se adapta vía QSS)

        # --- Navegación ---
        self._btn_first = _make_button(_icon_first(c), "Primera página (Home)")
        self._btn_prev = _make_button(_icon_prev(c), "Anterior (Left)")
        self._lbl_page_info = QLabel(" 0 / 0 ")
        self._lbl_page_info.setObjectName("pageInfoLabel")
        self._lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_page_info.setMinimumWidth(90)
        self._btn_next = _make_button(_icon_next(c), "Siguiente (Right)")
        self._btn_last = _make_button(_icon_last(c), "Última página (End)")

        self._btn_next_bc = _make_button(
            _icon_next_barcode(c), "Siguiente con barcode",
        )
        self._btn_next_review = _make_button(
            _icon_next_review(c), "Siguiente pendiente revisión",
        )

        layout.addWidget(self._btn_first)
        layout.addWidget(self._btn_prev)
        layout.addWidget(self._lbl_page_info)
        layout.addWidget(self._btn_next)
        layout.addWidget(self._btn_last)
        layout.addWidget(self._btn_next_bc)
        layout.addWidget(self._btn_next_review)

        # Separador
        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # Navegación programable
        self._btn_nav_script = _make_button(
            _icon_nav_script(c), "Navegación programable (script)",
        )
        layout.addWidget(self._btn_nav_script)

        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # --- Zoom ---
        self._btn_zoom_in = _make_button(_icon_zoom_in(c), "Acercar (Ctrl++)")
        self._btn_zoom_out = _make_button(_icon_zoom_out(c), "Alejar (Ctrl+-)")
        self._btn_zoom_fit = _make_button(
            _icon_zoom_fit(c), "Ajustar a página (Ctrl+F)",
        )
        self._btn_zoom_100 = _make_button(
            _icon_zoom_100(c), "Tamaño real", width=42,
        )

        layout.addWidget(self._btn_zoom_in)
        layout.addWidget(self._btn_zoom_out)
        layout.addWidget(self._btn_zoom_fit)
        layout.addWidget(self._btn_zoom_100)

        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # --- Herramientas ---
        self._btn_rotate = _make_button(_icon_rotate(c), "Rotar 90°")
        self._btn_mark = _make_button(_icon_mark(c), "Marcar/desmarcar página")
        self._btn_delete_current = _make_button(
            _icon_delete_current(), "Eliminar página actual",
            obj_name="dangerButton",
        )
        self._btn_delete_from = _make_button(
            _icon_delete_from(), "Borrar desde aquí",
            obj_name="dangerButton",
        )

        layout.addWidget(self._btn_rotate)
        layout.addWidget(self._btn_mark)
        layout.addWidget(self._btn_delete_current)
        layout.addWidget(self._btn_delete_from)

        # Conexiones internas
        self._btn_first.clicked.connect(self.nav_first)
        self._btn_prev.clicked.connect(self.nav_prev)
        self._btn_next.clicked.connect(self.nav_next)
        self._btn_last.clicked.connect(self.nav_last)
        self._btn_next_bc.clicked.connect(self.nav_next_barcode)
        self._btn_next_review.clicked.connect(self.nav_next_review)
        self._btn_nav_script.clicked.connect(self.nav_script)
        self._btn_zoom_in.clicked.connect(self.zoom_in_requested)
        self._btn_zoom_out.clicked.connect(self.zoom_out_requested)
        self._btn_zoom_fit.clicked.connect(self.zoom_fit_requested)
        self._btn_zoom_100.clicked.connect(self.zoom_100_requested)
        self._btn_rotate.clicked.connect(self.rotate_requested)
        self._btn_mark.clicked.connect(self.mark_requested)
        self._btn_delete_current.clicked.connect(self.delete_current_requested)
        self._btn_delete_from.clicked.connect(self.delete_from_requested)

    def update_page_info(self, current: int, total: int) -> None:
        """Actualiza el indicador de página."""
        self._lbl_page_info.setText(f" {current} / {total} ")

    def update_icon_color(self, color: str) -> None:
        """Regenera los iconos con un color nuevo (al cambiar tema)."""
        self._btn_first.setIcon(_icon_first(color))
        self._btn_prev.setIcon(_icon_prev(color))
        self._btn_next.setIcon(_icon_next(color))
        self._btn_last.setIcon(_icon_last(color))
        self._btn_next_bc.setIcon(_icon_next_barcode(color))
        self._btn_next_review.setIcon(_icon_next_review(color))
        self._btn_nav_script.setIcon(_icon_nav_script(color))
        self._btn_zoom_in.setIcon(_icon_zoom_in(color))
        self._btn_zoom_out.setIcon(_icon_zoom_out(color))
        self._btn_zoom_fit.setIcon(_icon_zoom_fit(color))
        self._btn_zoom_100.setIcon(_icon_zoom_100(color))
        self._btn_rotate.setIcon(_icon_rotate(color))
        self._btn_mark.setIcon(_icon_mark(color))

    def _separator(self) -> QWidget:
        """Crea un separador vertical delgado."""
        sep = QWidget()
        sep.setFixedSize(1, 28)
        sep.setObjectName("overlaySeparator")
        return sep
