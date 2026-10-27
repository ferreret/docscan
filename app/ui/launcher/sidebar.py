"""Sidebar colapsable para el Launcher.

Panel lateral izquierdo con dos estados:
- Colapsado: solo iconos (~48px)
- Expandido: iconos + texto (~200px)
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from app.ui.icons import svg_icon
from app.ui.palette import palette
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
# Iconos del sidebar (Lucide, ver app/ui/icons.py)
# ---------------------------------------------------------------


def _lucide(name: str):
    """Fábrica ``(color, size) -> QIcon`` para un icono Lucide."""

    def factory(color: str, size: int = _ICON_SIZE) -> QIcon:
        return svg_icon(name, color, size)

    return factory


_icon_plus = _lucide("plus")
_icon_folder_open = _lucide("folder-open")
_icon_gear = _lucide("settings")
_icon_copy = _lucide("copy")
_icon_upload = _lucide("upload")
_icon_download = _lucide("download")
_icon_trash = _lucide("trash-2")
_icon_refresh = _lucide("refresh-cw")
_icon_grid = _lucide("layout-grid")
_icon_ai = _lucide("sparkles")
_icon_info = _lucide("info")
_icon_hamburger = _lucide("menu")


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
        return palette(self._is_dark)["text"]

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(2)

        color = self._icon_color()

        # Toggle
        self._btn_toggle = _SidebarButton(
            _icon_hamburger(color),
            "Menu",
            self,
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

        # fixedWidth no es una propiedad animable; animamos minimumWidth/maximumWidth en paralelo
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
