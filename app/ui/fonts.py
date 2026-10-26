"""Tipografía de la interfaz.

En Windows se usa «Segoe UI», como FlexibarNET 10. En el resto de sistemas
esa fuente no existe y Qt caía en la que hubiera (Ubuntu, DejaVu…), así que
se empaqueta **Inter** (OFL, ``resources/fonts/inter``) y se registra al
arrancar para que la interfaz se vea igual en cualquier equipo Linux.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase

log = logging.getLogger(__name__)

_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "fonts"
PREFERRED_FAMILIES = ("Segoe UI", "Inter")


def register_fonts() -> list[str]:
    """Registra en Qt las fuentes empaquetadas.

    Debe llamarse después de crear la ``QApplication``.

    Returns:
        Familias registradas (vacía si no se encontró ninguna).
    """
    families: set[str] = set()
    for font_file in sorted(_FONTS_DIR.rglob("*.otf")) + sorted(
        _FONTS_DIR.rglob("*.ttf")
    ):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            log.warning("No se pudo registrar la fuente %s", font_file.name)
            continue
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    if families:
        log.info("Fuentes registradas: %s", ", ".join(sorted(families)))
    return sorted(families)


def ui_font_family() -> str:
    """Familia de la interfaz: la primera de ``PREFERRED_FAMILIES`` disponible."""
    available = set(QFontDatabase.families())
    for family in PREFERRED_FAMILIES:
        if family in available:
            return family
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
