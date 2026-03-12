"""Gestor de temas claro/oscuro y tamaño de fuente para DocScan Studio."""

from __future__ import annotations

import logging
import re
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

_STYLES_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "styles"

BASE_FONT_SIZE = 13
MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 22


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"


class ThemeManager(QObject):
    """Gestor singleton de temas de la aplicación.

    Signals:
        theme_changed: Emitida cuando cambia el tema activo.
        font_size_changed: Emitida cuando cambia el tamaño de fuente.
    """

    theme_changed = Signal(str)
    font_size_changed = Signal(int)

    _instance: ThemeManager | None = None

    def __new__(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True
        self._current_theme = Theme.DARK
        self._font_size = BASE_FONT_SIZE

    @property
    def current_theme(self) -> Theme:
        return self._current_theme

    @property
    def is_dark(self) -> bool:
        return self._current_theme == Theme.DARK

    @property
    def font_size(self) -> int:
        return self._font_size

    def apply_theme(self, theme: Theme) -> None:
        """Aplica un tema a la aplicación."""
        qss_file = _STYLES_DIR / f"{theme.value}.qss"
        if not qss_file.exists():
            log.warning("Archivo de tema no encontrado: %s", qss_file)
            return

        stylesheet = qss_file.read_text(encoding="utf-8")
        stylesheet = self._scale_font_sizes(stylesheet)

        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        self._current_theme = theme
        self.theme_changed.emit(theme.value)
        log.info("Tema aplicado: %s (fuente: %dpx)", theme.value, self._font_size)

    def toggle_theme(self) -> None:
        """Alterna entre tema claro y oscuro."""
        new_theme = Theme.LIGHT if self._current_theme == Theme.DARK else Theme.DARK
        self.apply_theme(new_theme)

    def increase_font(self) -> None:
        """Aumenta el tamaño de fuente en 1px."""
        if self._font_size < MAX_FONT_SIZE:
            self._font_size += 1
            self._reapply()
            self.font_size_changed.emit(self._font_size)

    def decrease_font(self) -> None:
        """Reduce el tamaño de fuente en 1px."""
        if self._font_size > MIN_FONT_SIZE:
            self._font_size -= 1
            self._reapply()
            self.font_size_changed.emit(self._font_size)

    def _reapply(self) -> None:
        """Re-aplica el tema actual con el nuevo tamaño de fuente."""
        self.apply_theme(self._current_theme)

    def _scale_font_sizes(self, stylesheet: str) -> str:
        """Escala todos los font-size del QSS según el delta actual."""
        delta = self._font_size - BASE_FONT_SIZE

        def _replace(match: re.Match) -> str:
            original = int(match.group(1))
            scaled = max(MIN_FONT_SIZE, original + delta)
            return f"font-size: {scaled}px"

        return re.sub(r"font-size:\s*(\d+)px", _replace, stylesheet)
