"""Iconos de la barra superior (tema y tamaño de fuente).

Envoltorio sobre los iconos Lucide de ``app/ui/icons.py`` que conserva la
API anterior (antes se dibujaban a mano con QPainter). Sin color explícito,
cada icono toma el de la paleta del tema activo.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon

from app.ui.icons import svg_icon


def _default(role: str) -> str:
    from app.ui.palette import color

    return color(role)


def icon_sun(color: str | None = None, size: int = 32) -> QIcon:
    """Icono de sol (pasar a tema claro)."""
    return svg_icon("sun", color or _default("yellow"), size)


def icon_moon(color: str | None = None, size: int = 32) -> QIcon:
    """Icono de luna (pasar a tema oscuro)."""
    return svg_icon("moon", color or _default("subtext0"), size)


def icon_font_increase(color: str | None = None, size: int = 32) -> QIcon:
    """Icono A+ (aumentar fuente)."""
    return svg_icon("a-arrow-up", color or _default("text"), size)


def icon_font_decrease(color: str | None = None, size: int = 32) -> QIcon:
    """Icono A- (reducir fuente)."""
    return svg_icon("a-arrow-down", color or _default("text"), size)
