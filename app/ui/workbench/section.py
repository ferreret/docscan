"""Sección plegable del panel derecho del Workbench.

Cabecera «TÍTULO · N» en versalitas, con hueco para botones propios y un
chevron que pliega o despliega el cuerpo; el cuerpo crece con su contenido
hasta un tope y a partir de ahí hace scroll. Es el patrón de los paneles
«Barcodes de la página» y «Campos de lote» de FlexibarNET 10. El plegado dura
lo que la sesión (no se guarda), como allí.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon


class CollapsibleSection(QFrame):
    """Panel con cabecera, contador, botones y cuerpo plegable con tope de alto.

    Signals:
        collapsed_changed: True al plegarse, False al desplegarse.
    """

    collapsed_changed = Signal(bool)

    def __init__(
        self,
        title: str,
        body: QWidget,
        *,
        max_body_height: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("panelSection")
        self._title = title
        self._collapsed = False
        self._max_body_height = max_body_height

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._lbl_title = QLabel()
        self._lbl_title.setObjectName("sectionTitle")
        header.addWidget(self._lbl_title)
        header.addStretch(1)
        self._header_actions = QHBoxLayout()
        self._header_actions.setSpacing(6)
        header.addLayout(self._header_actions)
        self._btn_toggle = QPushButton()
        self._btn_toggle.setObjectName("sectionToggle")
        self._btn_toggle.setFixedSize(24, 22)
        self._btn_toggle.setIconSize(QSize(14, 14))
        self._btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle.clicked.connect(self.toggle)
        header.addWidget(self._btn_toggle)
        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("sectionBody")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(body)
        layout.addWidget(self._scroll)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.set_count(0)
        self._refresh_toggle()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def add_header_widget(self, widget: QWidget) -> None:
        """Añade un botón u otro widget a la derecha de la cabecera."""
        self._header_actions.addWidget(widget)

    def set_count(self, count: int) -> None:
        """Actualiza el contador de la cabecera («TÍTULO · N»)."""
        self._lbl_title.setText(f"{self._title.upper()} · {count}")

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Pliega o despliega el cuerpo."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._scroll.setVisible(not collapsed)
        self._refresh_toggle()
        self.collapsed_changed.emit(collapsed)

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def fit_body(self) -> None:
        """Ajusta el alto del cuerpo a su contenido, sin pasar del tope."""
        body = self._scroll.widget()
        layout = body.layout()
        if layout is not None:
            # Medir con el layout recién recalculado: si no, se mide el
            # contenido anterior (filas aún sin colocar).
            layout.invalidate()
            layout.activate()
            wanted = layout.sizeHint().height() + 2
        else:
            body.adjustSize()
            wanted = body.sizeHint().height() + 2
        self._scroll.setFixedHeight(max(0, min(wanted, self._max_body_height)))

    def refresh_icons(self) -> None:
        """Repinta el chevron con la paleta del tema activo."""
        self._refresh_toggle()

    # ------------------------------------------------------------------

    def _refresh_toggle(self) -> None:
        name = "chevron-down" if self._collapsed else "chevron-up"
        self._btn_toggle.setIcon(icon(name, "subtext0", 14))
        self._btn_toggle.setToolTip(
            self.tr("Mostrar la lista")
            if self._collapsed
            else self.tr("Ocultar la lista")
        )
