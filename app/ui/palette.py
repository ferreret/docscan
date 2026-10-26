"""Paleta de colores de DocScan Studio: fuente única para QSS y Python.

Los valores son los de FlexibarNET 10 (``Themes/Palette.{Dark,Light}.xaml``):
navy profundo en oscuro y el claro de Flexibar, con sus mismas claves base
(``base``, ``surface0``, ``blue``…). Encima se definen los roles semánticos
que usa la plantilla ``resources/styles/theme.qss`` (``$field``,
``$on_accent``…), de modo que un rol puede cambiar de color sin tocar el QSS.

El código Python no debe escribir colores literales: los pide aquí con
``color("blue")`` o ``color("text_muted")``, que devuelve el del tema activo.
"""

from __future__ import annotations

from typing import Final

# ------------------------------------------------------------------
# Colores base (claves de FlexibarNET 10)
# ------------------------------------------------------------------

_BASE_DARK: Final[dict[str, str]] = {
    "base": "#0d1422",
    "mantle": "#0a0f1b",
    "crust": "#070b13",
    "surface0": "#141d2f",
    "surface1": "#1e2a40",
    "surface2": "#2b3a55",
    "overlay0": "#9fadc7",
    "subtext0": "#c2cde2",
    "text": "#e3eaf7",
    "blue": "#60a5fa",
    "red": "#f0718c",
    "green": "#4ade80",
    "yellow": "#facc6b",
    "peach": "#fb9d6a",
    "orange": "#f97316",
    "mauve": "#a78bfa",
    "hover": "#1a2538",
    "danger_hover": "#3a1b28",
}

_BASE_LIGHT: Final[dict[str, str]] = {
    "base": "#fafbfc",
    "mantle": "#f2f4f8",
    "crust": "#e8ebf1",
    "surface0": "#e4e7ee",
    "surface1": "#d4d8e1",
    "surface2": "#bec3cf",
    "overlay0": "#5d6175",
    "subtext0": "#3f4258",
    "text": "#3b3f57",
    "blue": "#1e66f5",
    "red": "#d20f39",
    "green": "#40a02b",
    "yellow": "#d19007",
    "peach": "#eb6a0b",
    "orange": "#e06000",
    "mauve": "#8839ef",
    "hover": "#d4d8e1",
    "danger_hover": "#fadde3",
}


def _roles(b: dict[str, str], dark: bool) -> dict[str, str]:
    """Roles semánticos de la plantilla QSS a partir de los colores base."""
    return {
        # Fondos
        "bg": b["base"],
        "bg_alt": b["mantle"],
        "bg_raised": b["surface0"] if dark else b["mantle"],
        "code_bg": b["mantle"] if dark else "#ffffff",
        "disabled_bg": b["base"] if dark else b["mantle"],
        "hover": b["hover"] if dark else "#eef1f6",
        "hover_alt": b["hover"] if dark else b["crust"],
        # Superficies
        "surface": b["surface0"],
        "surface_btn": b["surface0"] if dark else b["crust"],
        "surface_active": b["surface1"] if dark else b["surface0"],
        "field": b["surface0"] if dark else "#ffffff",
        "selection_bg": b["surface1"] if dark else "#e7effd",
        "hover_strong": b["surface2"] if dark else b["surface1"],
        "pressed": b["surface2"] if dark else b["surface1"],
        "spin_hover": b["surface2"] if dark else "#dce4f7",
        "overlay_btn": "rgba(30, 42, 64, 180)" if dark else "rgba(212, 216, 225, 200)",
        # Bordes
        "border": b["surface1"],
        "border_soft": b["surface1"] if dark else b["surface0"],
        "border_strong": b["surface2"],
        "sidebar_border": b["surface0"] if dark else b["surface1"],
        "overlay_btn_border": b["surface2"],
        # Texto
        "text": b["text"],
        "text_muted": b["subtext0"],
        "text_secondary": b["subtext0"],
        "text_muted_hover": b["text"],
        "text_subtle": b["overlay0"],
        "text_placeholder": b["overlay0"] if dark else "#7a7f93",
        "text_hint": b["overlay0"],
        "text_disabled": "#4b5b78" if dark else "#a0a6b5",
        # Acento y estados
        "accent": b["blue"],
        "accent_hover": "#93c5fd" if dark else "#4080f7",
        "on_accent": b["base"] if dark else "#ffffff",
        "danger": b["red"],
        "danger_bg": b["danger_hover"],
        "danger_btn": "#d20f39",
        "warning": b["yellow"],
        "on_warning": b["base"] if dark else "white",
        "success_btn": "#40a02b",
        # Banner informativo (actualizaciones)
        "info_bg": "#1e2a3a" if dark else "#e7effd",
        "info_fg": "#89b4fa" if dark else "#1e40af",
        "info_border": "#3b82f6",
        "banner_btn": "#2563eb",
        "banner_btn_hover": "#2563eb" if dark else "#bfdbfe",
        "banner_btn_strong": "#3b82f6" if dark else "#1d4ed8",
        "banner_hover_text": "white" if dark else "#1e40af",
        # Recursos y tipografía
        "arrow_variant": "dark" if dark else "light",
        # Segoe UI en Windows (como Flexibar); Inter, empaquetada, en el resto.
        "font_family": '"Segoe UI", "Inter", sans-serif',
    }


DARK: Final[dict[str, str]] = {**_BASE_DARK, **_roles(_BASE_DARK, dark=True)}
LIGHT: Final[dict[str, str]] = {**_BASE_LIGHT, **_roles(_BASE_LIGHT, dark=False)}


def palette(dark: bool) -> dict[str, str]:
    """Paleta completa (colores base + roles) del tema pedido."""
    return DARK if dark else LIGHT


def color(name: str) -> str:
    """Color ``name`` del tema activo.

    Args:
        name: Clave base (``"blue"``, ``"surface1"``…) o rol (``"text_muted"``).

    Raises:
        KeyError: Si la clave no existe en la paleta.
    """
    from app.ui.theme_manager import ThemeManager

    return palette(ThemeManager().is_dark)[name]
