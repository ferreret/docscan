"""Sidebar colapsable para el Launcher.

Panel lateral izquierdo con dos estados:
- Colapsado: solo iconos (~48px)
- Expandido: iconos + texto (~200px)
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPoint, QPropertyAnimation, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_COLLAPSED_W = 48
_EXPANDED_W = 200
_ICON_SIZE = 24
_BTN_H = 40


# ---------------------------------------------------------------
# Fabrica de iconos para el sidebar
# ---------------------------------------------------------------

def _pm(size: int = _ICON_SIZE) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _icon_plus(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono + (Nueva)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(2, size / 10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    c = size // 2
    arm = int(size * 0.3)
    p.drawLine(c - arm, c, c + arm, c)
    p.drawLine(c, c - arm, c, c + arm)
    p.end()
    return QIcon(pm)


def _icon_folder_open(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono carpeta abierta (Abrir)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(size * 0.15)
    # Carpeta
    p.drawRect(m, int(size * 0.3), size - 2 * m, int(size * 0.5))
    # Pestaña
    p.drawLine(m, int(size * 0.3), int(size * 0.35), int(size * 0.3))
    p.drawLine(int(size * 0.35), int(size * 0.3), int(size * 0.45), int(size * 0.18))
    p.drawLine(int(size * 0.45), int(size * 0.18), int(size * 0.6), int(size * 0.18))
    p.end()
    return QIcon(pm)


def _icon_gear(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono engranaje (Configurar)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    pen = QPen(c, max(1.5, size / 14))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = size // 2, size // 2
    r_outer = int(size * 0.38)
    r_inner = int(size * 0.18)
    # Circulo interior
    p.drawEllipse(QPoint(cx, cy), r_inner, r_inner)
    # Dientes
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + int(r_inner * 1.3 * math.cos(angle))
        y1 = cy + int(r_inner * 1.3 * math.sin(angle))
        x2 = cx + int(r_outer * math.cos(angle))
        y2 = cy + int(r_outer * math.sin(angle))
        p.drawLine(x1, y1, x2, y2)
    p.end()
    return QIcon(pm)


def _icon_copy(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono copiar (Clonar)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(size * 0.12)
    offset = int(size * 0.18)
    w = int(size * 0.55)
    # Rectangulo trasero
    p.drawRect(m + offset, m, w, w)
    # Rectangulo frontal
    p.drawRect(m, m + offset, w, w)
    p.end()
    return QIcon(pm)


def _icon_upload(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono exportar (flecha arriba + caja)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    cx = size // 2
    # Flecha arriba
    top = int(size * 0.15)
    mid = int(size * 0.55)
    arm = int(size * 0.18)
    p.drawLine(cx, top, cx, mid)
    p.drawLine(cx, top, cx - arm, top + arm)
    p.drawLine(cx, top, cx + arm, top + arm)
    # Caja
    m = int(size * 0.15)
    btm = int(size * 0.82)
    p.drawLine(m, int(size * 0.45), m, btm)
    p.drawLine(m, btm, size - m, btm)
    p.drawLine(size - m, btm, size - m, int(size * 0.45))
    p.end()
    return QIcon(pm)


def _icon_download(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono importar (flecha abajo + caja)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    cx = size // 2
    top = int(size * 0.15)
    mid = int(size * 0.55)
    arm = int(size * 0.18)
    # Flecha abajo
    p.drawLine(cx, top, cx, mid)
    p.drawLine(cx, mid, cx - arm, mid - arm)
    p.drawLine(cx, mid, cx + arm, mid - arm)
    # Caja
    m = int(size * 0.15)
    btm = int(size * 0.82)
    p.drawLine(m, int(size * 0.45), m, btm)
    p.drawLine(m, btm, size - m, btm)
    p.drawLine(size - m, btm, size - m, int(size * 0.45))
    p.end()
    return QIcon(pm)


def _icon_trash(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono papelera (Eliminar)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(size * 0.2)
    # Tapa
    p.drawLine(m - 2, int(size * 0.28), size - m + 2, int(size * 0.28))
    p.drawLine(int(size * 0.38), int(size * 0.28), int(size * 0.38), int(size * 0.15))
    p.drawLine(int(size * 0.38), int(size * 0.15), int(size * 0.62), int(size * 0.15))
    p.drawLine(int(size * 0.62), int(size * 0.15), int(size * 0.62), int(size * 0.28))
    # Cuerpo
    p.drawLine(m, int(size * 0.28), int(m * 1.15), int(size * 0.85))
    p.drawLine(int(m * 1.15), int(size * 0.85), int(size - m * 1.15), int(size * 0.85))
    p.drawLine(int(size - m * 1.15), int(size * 0.85), size - m, int(size * 0.28))
    p.end()
    return QIcon(pm)


def _icon_refresh(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono actualizar (flecha circular)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    cx, cy = size // 2, size // 2
    r = int(size * 0.32)
    p.drawArc(cx - r, cy - r, 2 * r, 2 * r, 30 * 16, 300 * 16)
    # Punta de flecha
    tip_angle = math.radians(30)
    tx = cx + int(r * math.cos(tip_angle))
    ty = cy - int(r * math.sin(tip_angle))
    arm = int(size * 0.12)
    p.drawLine(tx, ty, tx + arm, ty + arm)
    p.drawLine(tx, ty, tx - arm, ty + int(arm * 0.3))
    p.end()
    return QIcon(pm)


def _icon_grid(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono grid (Gestor de lotes)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(size * 0.15)
    gap = int(size * 0.08)
    cell = (size - 2 * m - gap) // 2
    for row in range(2):
        for col in range(2):
            x = m + col * (cell + gap)
            y = m + row * (cell + gap)
            p.drawRect(x, y, cell, cell)
    p.end()
    return QIcon(pm)


def _icon_ai(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono AI (estrella/sparkle)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    c = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    cx, cy = size // 2, size // 2
    r = int(size * 0.38)
    # Estrella de 4 puntas
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF
    pts = []
    for i in range(8):
        angle = math.radians(i * 45 - 90)
        dist = r if i % 2 == 0 else int(r * 0.35)
        pts.append(QPointF(cx + dist * math.cos(angle), cy + dist * math.sin(angle)))
    p.drawPolygon(QPolygonF(pts))
    p.end()
    return QIcon(pm)


def _icon_info(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono (i) información (Acerca de)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.5, size / 14))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    c = size // 2
    r = int(size * 0.38)
    p.drawEllipse(QPoint(c, c), r, r)
    # Punto de la i
    dot_r = max(1, int(size * 0.05))
    p.setBrush(QColor(color))
    p.drawEllipse(QPoint(c, int(c - r * 0.45)), dot_r, dot_r)
    # Barra de la i
    pen2 = QPen(QColor(color), max(2, size / 10))
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    p.drawLine(c, int(c - r * 0.15), c, int(c + r * 0.55))
    p.end()
    return QIcon(pm)


def _icon_hamburger(color: str, size: int = _ICON_SIZE) -> QIcon:
    """Icono hamburguesa (toggle sidebar)."""
    pm = _pm(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(2, size / 10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = int(size * 0.2)
    for i, frac in enumerate([0.3, 0.5, 0.7]):
        y = int(size * frac)
        p.drawLine(m, y, size - m, y)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------
# SidebarButton
# ---------------------------------------------------------------

class _SidebarButton(QPushButton):
    """Boton del sidebar con icono y texto opcional."""

    def __init__(
        self,
        icon: QIcon,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label_text = text
        self.setIcon(icon)
        self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.setFixedHeight(_BTN_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)
        self.setObjectName("sidebarBtn")
        self._expanded = False
        self._update_text()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._update_text()

    def _update_text(self) -> None:
        if self._expanded:
            self.setText(f"  {self._label_text}")
            self.setStyleSheet("text-align: left; padding-left: 8px;")
        else:
            self.setText("")
            self.setStyleSheet("")


# ---------------------------------------------------------------
# Sidebar widget
# ---------------------------------------------------------------

class Sidebar(QWidget):
    """Panel lateral colapsable con iconos/texto.

    Signals:
        action_triggered: Emitida con el nombre de la accion.
    """

    action_triggered = Signal(str)

    def __init__(self, is_dark: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._expanded = False
        self._is_dark = is_dark
        self._buttons: dict[str, _SidebarButton] = {}
        self.setFixedWidth(_COLLAPSED_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _icon_color(self) -> str:
        return "#cdd6f4" if self._is_dark else "#4c4f69"

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(2)

        color = self._icon_color()

        # Toggle
        self._btn_toggle = _SidebarButton(
            _icon_hamburger(color), "Menu", self,
        )
        self._btn_toggle.setObjectName("sidebarToggle")
        self._btn_toggle.clicked.connect(self._toggle)
        layout.addWidget(self._btn_toggle)

        layout.addSpacing(8)

        # Acciones principales
        actions = [
            ("new", _icon_plus(color), "Nueva"),
            ("open", _icon_folder_open(color), "Abrir"),
            ("configure", _icon_gear(color), "Configurar"),
            ("clone", _icon_copy(color), "Clonar"),
            ("export", _icon_upload(color), "Exportar"),
            ("import", _icon_download(color), "Importar"),
            ("delete", _icon_trash(color), "Eliminar"),
        ]

        for name, icon, text in actions:
            btn = _SidebarButton(icon, text, self)
            btn.clicked.connect(lambda _, n=name: self.action_triggered.emit(n))
            self._buttons[name] = btn
            layout.addWidget(btn)

        # Separador visual
        layout.addSpacing(12)

        # Acciones secundarias
        secondary = [
            ("refresh", _icon_refresh(color), "Actualizar"),
            ("batch_manager", _icon_grid(color), "Gestor de Lotes"),
            ("ai_mode", _icon_ai(color), "AI MODE"),
        ]

        for name, icon, text in secondary:
            btn = _SidebarButton(icon, text, self)
            btn.clicked.connect(lambda _, n=name: self.action_triggered.emit(n))
            self._buttons[name] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Botón "Acerca de" al final
        btn_about = _SidebarButton(_icon_info(color), "Acerca de", self)
        btn_about.clicked.connect(lambda _: self.action_triggered.emit("about"))
        self._buttons["about"] = btn_about
        layout.addWidget(btn_about)

        # Marcar delete como danger
        if "delete" in self._buttons:
            self._buttons["delete"].setObjectName("sidebarBtnDanger")

        # AI MODE es checkable
        if "ai_mode" in self._buttons:
            self._buttons["ai_mode"].setCheckable(True)
            self._buttons["ai_mode"].setObjectName("sidebarBtnAiMode")

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        target_w = _EXPANDED_W if self._expanded else _COLLAPSED_W

        anim = QPropertyAnimation(self, b"fixedWidth")
        # fixedWidth no es una propiedad directa, usamos minimumWidth/maximumWidth
        self._anim = QPropertyAnimation(self, b"minimumWidth")
        self._anim.setDuration(150)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target_w)
        self._anim.start()

        self._anim2 = QPropertyAnimation(self, b"maximumWidth")
        self._anim2.setDuration(150)
        self._anim2.setStartValue(self.width())
        self._anim2.setEndValue(target_w)
        self._anim2.start()

        for btn in self._buttons.values():
            btn.set_expanded(self._expanded)
        self._btn_toggle.set_expanded(self._expanded)

    def set_button_enabled(self, name: str, enabled: bool) -> None:
        """Habilita/deshabilita un boton por nombre."""
        btn = self._buttons.get(name)
        if btn:
            btn.setEnabled(enabled)

    def is_ai_mode_checked(self) -> bool:
        btn = self._buttons.get("ai_mode")
        return btn.isChecked() if btn else False

    def get_button(self, name: str) -> QPushButton | None:
        return self._buttons.get(name)

    def update_theme(self, is_dark: bool) -> None:
        """Actualiza los iconos al cambiar de tema."""
        self._is_dark = is_dark
        color = self._icon_color()
        # Recrear iconos
        icon_map = {
            "new": _icon_plus,
            "open": _icon_folder_open,
            "configure": _icon_gear,
            "clone": _icon_copy,
            "export": _icon_upload,
            "import": _icon_download,
            "delete": _icon_trash,
            "refresh": _icon_refresh,
            "batch_manager": _icon_grid,
            "ai_mode": _icon_ai,
            "about": _icon_info,
        }
        for name, icon_fn in icon_map.items():
            btn = self._buttons.get(name)
            if btn:
                btn.setIcon(icon_fn(color))
        self._btn_toggle.setIcon(_icon_hamburger(color))
