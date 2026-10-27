"""Iconos de la interfaz: Lucide recoloreado con la paleta.

Un único juego de iconos de trazo fino y monocromo (Lucide, ISC, en
``resources/icons/lucide``), el más parecido a los Segoe Fluent Icons de
FlexibarNET 10, que solo existen en Windows y no se pueden redistribuir.
Sustituye a los ~30 iconos que se dibujaban a mano con ``QPainter`` en tres
ficheros, cada uno con su grosor y su color.

Los SVG de Lucide pintan con ``currentColor``; aquí se sustituye por el color
pedido antes de rasterizar, y el resultado se cachea por (icono, color,
tamaño). El estado deshabilitado se genera con el color ``text_disabled``.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

log = logging.getLogger(__name__)

_ICONS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "resources" / "icons" / "lucide"
)
DEFAULT_SIZE = 20
# Lucide trae stroke-width 2 a 24 px; algo más fino se ve más nítido a los
# 16-20 px de las barras, como el trazo de Segoe Fluent en Flexibar.
DEFAULT_STROKE = 1.75


@lru_cache(maxsize=None)
def _svg_source(name: str) -> str:
    path = _ICONS_DIR / f"{name}.svg"
    if not path.exists():
        raise FileNotFoundError(f"Icono '{name}' no está en {_ICONS_DIR}")
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=512)
def _pixmap(name: str, color: str, size: int, stroke: float) -> QPixmap:
    svg = (
        _svg_source(name)
        .replace("currentColor", color)
        .replace('stroke-width="2"', f'stroke-width="{stroke}"')
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    ratio = max(ratio, 2.0)  # nitidez también al escalar en pantallas HiDPI
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pm.width(), pm.height()))
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def svg_icon(
    name: str,
    color: str,
    size: int = DEFAULT_SIZE,
    *,
    stroke: float = DEFAULT_STROKE,
    disabled_color: str | None = None,
) -> QIcon:
    """Icono Lucide ``name`` pintado en un color concreto.

    Args:
        name: Nombre del fichero en ``resources/icons/lucide`` (sin ``.svg``).
        color: Color CSS del trazo (``#rrggbb``).
        size: Lado en píxeles lógicos.
        stroke: Grosor del trazo.
        disabled_color: Color para el estado deshabilitado (si no, Qt lo
            atenúa a su manera).
    """
    icon = QIcon(_pixmap(name, color, size, stroke))
    if disabled_color:
        icon.addPixmap(_pixmap(name, disabled_color, size, stroke), QIcon.Mode.Disabled)
    return icon


def icon(name: str, role: str = "text", size: int = DEFAULT_SIZE) -> QIcon:
    """Icono Lucide con un color de la paleta del tema activo.

    Args:
        name: Nombre del icono Lucide.
        role: Clave de ``app/ui/palette.py`` (``"text"``, ``"red"``, ``"orange"``…).
        size: Lado en píxeles lógicos.
    """
    from app.ui.palette import color

    return svg_icon(name, color(role), size, disabled_color=color("text_disabled"))


def available_icons() -> list[str]:
    """Nombres de los iconos empaquetados."""
    return sorted(p.stem for p in _ICONS_DIR.glob("*.svg"))
