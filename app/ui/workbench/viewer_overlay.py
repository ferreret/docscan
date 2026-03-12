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

_SZ = 24  # Tamaño base de los iconos


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
    p.setPen(_pen(color, 2.5))
    # Barra izquierda
    p.drawLine(5, 6, 5, 18)
    # Dos triángulos <<
    p.drawLine(14, 6, 8, 12)
    p.drawLine(8, 12, 14, 18)
    p.drawLine(20, 6, 14, 12)
    p.drawLine(14, 12, 20, 18)
    p.end()
    return QIcon(pm)


def _icon_prev(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawLine(16, 5, 8, 12)
    p.drawLine(8, 12, 16, 19)
    p.end()
    return QIcon(pm)


def _icon_next(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawLine(8, 5, 16, 12)
    p.drawLine(16, 12, 8, 19)
    p.end()
    return QIcon(pm)


def _icon_last(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    # Dos triángulos >>
    p.drawLine(4, 6, 10, 12)
    p.drawLine(10, 12, 4, 18)
    p.drawLine(10, 6, 16, 12)
    p.drawLine(16, 12, 10, 18)
    # Barra derecha
    p.drawLine(19, 6, 19, 18)
    p.end()
    return QIcon(pm)


def _icon_next_bc(color: str = "#cdd6f4") -> QIcon:
    """Siguiente con barcode: triángulo + barras verticales."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Triángulo
    p.drawLine(3, 6, 10, 12)
    p.drawLine(10, 12, 3, 18)
    # Mini barras de barcode
    for bx in (14, 17, 19, 21):
        p.drawLine(bx, 7, bx, 17)
    p.end()
    return QIcon(pm)


def _icon_next_review(color: str = "#cdd6f4") -> QIcon:
    """Siguiente pendiente: triángulo + signo de exclamación."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Triángulo
    p.drawLine(3, 6, 10, 12)
    p.drawLine(10, 12, 3, 18)
    # Exclamación
    pen2 = _pen("#fb8c00", 2.5)
    p.setPen(pen2)
    p.drawLine(18, 6, 18, 14)
    p.drawPoint(18, 18)
    p.end()
    return QIcon(pm)


# -- Iconos de zoom --

def _icon_zoom_in(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Lupa
    p.drawEllipse(QPoint(10, 10), 7, 7)
    p.drawLine(15, 15, 21, 21)
    # +
    p.drawLine(7, 10, 13, 10)
    p.drawLine(10, 7, 10, 13)
    p.end()
    return QIcon(pm)


def _icon_zoom_out(color: str = "#cdd6f4") -> QIcon:
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    p.drawEllipse(QPoint(10, 10), 7, 7)
    p.drawLine(15, 15, 21, 21)
    # -
    p.drawLine(7, 10, 13, 10)
    p.end()
    return QIcon(pm)


def _icon_zoom_fit(color: str = "#cdd6f4") -> QIcon:
    """Ajustar a página: 4 flechas hacia dentro."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Cuadrado central
    p.drawRect(7, 7, 10, 10)
    # Esquinas con flechitas
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        cx = 12 + dx * 8
        cy = 12 + dy * 8
        tx = 12 + dx * 5
        ty = 12 + dy * 5
        p.drawLine(cx, cy, tx, ty)
    p.end()
    return QIcon(pm)


def _icon_zoom_100(color: str = "#cdd6f4") -> QIcon:
    """1:1 como texto."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont("Segoe UI", 9)
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
    p.setPen(_pen(color, 2.0))
    # Arco (3/4 de círculo)
    p.drawArc(4, 4, 16, 16, 30 * 16, 300 * 16)
    # Flecha en la punta
    p.drawLine(18, 5, 20, 10)
    p.drawLine(18, 5, 14, 6)
    p.end()
    return QIcon(pm)


def _icon_mark(color: str = "#cdd6f4") -> QIcon:
    """Bandera para marcar/excluir."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Mástil
    p.drawLine(6, 4, 6, 20)
    # Bandera triangular
    p.setPen(_pen("#fb8c00", 2.0))
    p.setBrush(QColor("#fb8c00"))
    pts = [QPoint(7, 5), QPoint(19, 9), QPoint(7, 13)]
    p.drawPolygon(pts)
    p.end()
    return QIcon(pm)


def _icon_delete_current(color: str = "#e53935") -> QIcon:
    """X para eliminar página actual."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.5))
    p.drawLine(6, 6, 18, 18)
    p.drawLine(18, 6, 6, 18)
    p.end()
    return QIcon(pm)


def _icon_delete_from(color: str = "#e53935") -> QIcon:
    """Tijeras para borrar desde aquí."""
    pm = _pm()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color, 2.0))
    # Tijera: dos arcos + centro
    p.drawEllipse(QPoint(7, 17), 4, 4)
    p.drawEllipse(QPoint(17, 17), 4, 4)
    p.drawLine(9, 14, 17, 4)
    p.drawLine(15, 14, 7, 4)
    p.end()
    return QIcon(pm)


def _make_button(
    icon: QIcon,
    tooltip: str,
    *,
    width: int = 30,
    obj_name: str = "",
) -> QPushButton:
    """Crea un botón con icono pintado para el overlay."""
    btn = QPushButton()
    btn.setIcon(icon)
    btn.setToolTip(tooltip)
    btn.setFixedSize(width, 26)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if obj_name:
        btn.setObjectName(obj_name)
    return btn


class ViewerOverlay(QWidget):
    """Barra flotante de herramientas sobre el visor.

    Signals:
        nav_first, nav_prev, nav_next, nav_last: Navegación básica.
        nav_next_barcode, nav_next_review: Navegación inteligente.
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
        self._lbl_page_info.setMinimumWidth(60)
        self._btn_next = _make_button(_icon_next(c), "Siguiente (Right)")
        self._btn_last = _make_button(_icon_last(c), "Última página (End)")

        layout.addWidget(self._btn_first)
        layout.addWidget(self._btn_prev)
        layout.addWidget(self._lbl_page_info)
        layout.addWidget(self._btn_next)
        layout.addWidget(self._btn_last)

        # Separador
        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # Navegación inteligente
        self._btn_next_bc = _make_button(
            _icon_next_bc(c), "Siguiente con barcode", width=30,
        )
        self._btn_next_review = _make_button(
            _icon_next_review(c), "Siguiente pendiente revisión", width=30,
        )
        layout.addWidget(self._btn_next_bc)
        layout.addWidget(self._btn_next_review)

        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # --- Zoom ---
        self._btn_zoom_in = _make_button(_icon_zoom_in(c), "Acercar (Ctrl++)")
        self._btn_zoom_out = _make_button(_icon_zoom_out(c), "Alejar (Ctrl+-)")
        self._btn_zoom_fit = _make_button(
            _icon_zoom_fit(c), "Ajustar a página (Ctrl+F)",
        )
        self._btn_zoom_100 = _make_button(
            _icon_zoom_100(c), "Tamaño real", width=34,
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

    def _separator(self) -> QWidget:
        """Crea un separador vertical delgado."""
        sep = QWidget()
        sep.setFixedSize(1, 20)
        sep.setObjectName("overlaySeparator")
        return sep
