"""Popover de configuración del escáner del Workbench.

Paridad con FlexibarNET 10: el botón ⚙ junto a «Escanear» abre un panel
flotante con el escáner, la fuente y la casilla «Mostrar las opciones del
escáner al capturar». Se cierra al hacer clic fuera, como el ``Popup`` con
``StaysOpen=False`` de Flexibar. DocScan no tiene perfiles de escaneo, así
que la fila «Perfil» de Flexibar no existe aquí.

La lista de escáneres no se enumera al abrir el Workbench (en SANE puede
tardar varios segundos): se pide la primera vez que se abre el popover o
con el botón ↻.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.ui.icons import icon


class ScanConfigPopup(QFrame):
    """Panel flotante con la configuración de escaneo.

    Signals:
        refresh_requested: El usuario pide volver a buscar escáneres.
        config_changed: Ha cambiado el escáner, la fuente o la casilla.
    """

    refresh_requested = Signal()
    config_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("scanConfigPopup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._scanners_listed = False

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel(self.tr("Escáner:")), 0, 0)
        self.combo_source = QComboBox()
        self.combo_source.setMinimumWidth(280)
        self.combo_source.setPlaceholderText(self.tr("Sin escáner seleccionado"))
        grid.addWidget(self.combo_source, 0, 1)
        self._btn_refresh = QPushButton()
        self._btn_refresh.setObjectName("refreshScannersButton")
        self._btn_refresh.setIconSize(QSize(16, 16))
        self._btn_refresh.setFixedSize(30, 28)
        self._btn_refresh.setToolTip(self.tr("Volver a buscar escáneres"))
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.clicked.connect(self.refresh_requested)
        grid.addWidget(self._btn_refresh, 0, 2)

        grid.addWidget(QLabel(self.tr("Fuente:")), 1, 0)
        self.combo_source_type = QComboBox()
        self.combo_source_type.addItem(self.tr("Flatbed"), "flatbed")
        self.combo_source_type.addItem(self.tr("ADF"), "adf")
        grid.addWidget(self.combo_source_type, 1, 1, 1, 2)

        self.chk_show_options = QCheckBox(
            self.tr("Mostrar las opciones del escáner al capturar")
        )
        self.chk_show_options.setChecked(True)
        grid.addWidget(self.chk_show_options, 2, 0, 1, 3)

        self.combo_source.currentIndexChanged.connect(self.config_changed)
        self.combo_source_type.currentIndexChanged.connect(self.config_changed)
        self.chk_show_options.toggled.connect(self.config_changed)
        self.refresh_icons()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    @property
    def scanners_listed(self) -> bool:
        """True si ya se ha enumerado la lista de escáneres."""
        return self._scanners_listed

    def set_scanners(self, names: list[str]) -> None:
        """Rellena la lista de escáneres conservando el seleccionado."""
        current = self.combo_source.currentText()
        self.combo_source.blockSignals(True)
        self.combo_source.clear()
        self.combo_source.addItems(names)
        idx = self.combo_source.findText(current) if current else -1
        self.combo_source.setCurrentIndex(idx if idx >= 0 else (0 if names else -1))
        self.combo_source.blockSignals(False)
        self._scanners_listed = True
        self.config_changed.emit()

    def preselect_scanner(self, name: str) -> None:
        """Deja seleccionado ``name`` sin enumerar (escáner de la sesión anterior)."""
        if not name or self.combo_source.findText(name) >= 0:
            return
        self.combo_source.addItem(name)
        self.combo_source.setCurrentIndex(self.combo_source.count() - 1)

    def summary(self) -> str:
        """Texto del distintivo de la barra: escáner y fuente, o «sin escáner»."""
        name = self.combo_source.currentText()
        if not name:
            return self.tr("(sin escáner)")
        return f"{name} · {self.combo_source_type.currentText()}"

    def show_below(self, anchor: QWidget) -> None:
        """Abre el popover justo debajo de ``anchor``."""
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 6))
        self.move(pos)
        self.show()
        self.combo_source.setFocus(Qt.FocusReason.PopupFocusReason)

    def refresh_icons(self) -> None:
        """Repinta los iconos con la paleta del tema activo."""
        self._btn_refresh.setIcon(icon("refresh-cw", "text", 16))
