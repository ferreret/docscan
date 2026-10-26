"""Barra de herramientas del visor de documentos.

Contiene navegación, zoom y herramientas de manipulación. Se coloca en su
propia franja bajo el visor (WorkbenchWindow); ya no flota sobre la imagen,
porque tapaba la parte inferior de la página.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QIntValidator

from app.ui.icons import svg_icon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

log = logging.getLogger(__name__)

_SZ = 20  # Tamaño de los iconos (Lucide, trazo fino como en FlexibarNET10)
# Ancho que añade el QLineEdit del contador alrededor del texto: borde y
# padding del QSS más el margen interno de Qt.
_COUNTER_EDIT_CHROME = 10


def _lucide(name: str, default_role: str = "text"):
    """Fábrica ``(color) -> QIcon`` para un icono Lucide de la barra."""

    def factory(color: str | None = None) -> QIcon:
        from app.ui.palette import color as palette_color

        return svg_icon(
            name,
            color or palette_color(default_role),
            _SZ,
            disabled_color=palette_color("text_disabled"),
        )

    return factory


# -- Navegación --
_icon_first = _lucide("chevron-first")
_icon_prev = _lucide("chevron-left")
_icon_next = _lucide("chevron-right")
_icon_last = _lucide("chevron-last")
_icon_nav_script = _lucide("route")
_icon_next_barcode = _lucide("barcode")
_icon_next_review = _lucide("circle-alert")
# -- Zoom --
_icon_zoom_in = _lucide("zoom-in")
_icon_zoom_out = _lucide("zoom-out")
_icon_zoom_fit = _lucide("maximize")
_icon_zoom_100 = _lucide("proportions")
# -- Herramientas: el color se reserva para las acciones destructivas --
_icon_rotate = _lucide("rotate-cw")
_icon_mark = _lucide("flag")
_icon_delete_current = _lucide("trash-2", "red")
_icon_delete_from = _lucide("list-x", "red")


def _make_button(
    icon: QIcon,
    tooltip: str,
    *,
    width: int = 38,
    obj_name: str = "",
) -> QPushButton:
    """Crea un botón con icono pintado para el overlay."""
    btn = QPushButton()
    btn.setIcon(icon)
    btn.setIconSize(QSize(_SZ, _SZ))
    btn.setToolTip(tooltip)
    btn.setFixedSize(width, 32)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if obj_name:
        btn.setObjectName(obj_name)
    return btn


class _PageNumberEdit(QLineEdit):
    """Campo editable del contador de página.

    Intro confirma el salto (``returnPressed``); Escape o perder el foco
    cancelan y restauran el valor mostrado.

    Signals:
        cancelled: El usuario abandonó la edición sin confirmar.
    """

    cancelled = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        super().focusInEvent(event)
        # Diferido: el clic que da el foco deshace un selectAll() inmediato.
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        super().focusOutEvent(event)
        self.cancelled.emit()


class ViewerOverlay(QWidget):
    """Barra de herramientas del visor (va bajo la imagen, no sobre ella).

    Signals:
        nav_first, nav_prev, nav_next, nav_last: Navegación básica.
        page_jump_requested: Salto directo a una página (índice 0-based).
        nav_script: Navegación programable por script.
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
    nav_script = Signal()
    page_jump_requested = Signal(int)  # índice 0-based

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

        c = None  # color de la paleta del tema activo

        # --- Navegación ---
        self._btn_first = _make_button(
            _icon_first(c), self.tr("Primera p\u00e1gina (Home)")
        )
        self._btn_prev = _make_button(_icon_prev(c), self.tr("Anterior (Left)"))

        # Contador "N / M": la N es editable para saltar a una página
        # concreta sin recorrer el lote (clic, teclear, Intro).
        self._current_page = 0
        self._total_pages = 0
        self._edit_page = _PageNumberEdit("0")
        self._edit_page.setObjectName("pageInfoEdit")
        self._edit_page.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._edit_page.setValidator(QIntValidator(1, 999999, self._edit_page))
        self._edit_page.setToolTip(
            self.tr("Escribe un número de página y pulsa Intro para ir a ella")
        )
        self._lbl_page_info = QLabel("/ 0")
        self._lbl_page_info.setObjectName("pageInfoLabel")
        self._lbl_page_info.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._btn_next = _make_button(_icon_next(c), self.tr("Siguiente (Right)"))
        self._btn_last = _make_button(
            _icon_last(c), self.tr("\u00daltima p\u00e1gina (End)")
        )

        self._btn_next_bc = _make_button(
            _icon_next_barcode(c),
            self.tr("Siguiente con barcode (Ctrl+Right)"),
        )
        self._btn_next_review = _make_button(
            _icon_next_review(c),
            self.tr("Siguiente pendiente revisión (Ctrl+Shift+Right)"),
        )

        layout.addWidget(self._btn_first)
        layout.addWidget(self._btn_prev)
        # «N / M» como un bloque ajustado a su contenido y con el mismo margen
        # a cada lado, para que quede centrado entre las flechas.
        self._page_counter = QWidget()
        counter_layout = QHBoxLayout(self._page_counter)
        # 2 px menos a la izquierda: compensa el margen interno del QLineEdit,
        # que el «/ M» de la derecha no tiene (medido sobre la imagen).
        counter_layout.setContentsMargins(4, 0, 8, 0)
        counter_layout.setSpacing(4)
        counter_layout.addWidget(self._edit_page)
        counter_layout.addWidget(self._lbl_page_info)
        layout.addWidget(self._page_counter)
        self._fit_page_counter()
        layout.addWidget(self._btn_next)
        layout.addWidget(self._btn_last)
        layout.addWidget(self._btn_next_bc)
        layout.addWidget(self._btn_next_review)

        # Separador
        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # Navegación programable
        self._btn_nav_script = _make_button(
            _icon_nav_script(c),
            self.tr("Navegación programable (Ctrl+G)"),
        )
        layout.addWidget(self._btn_nav_script)

        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # --- Zoom ---
        self._btn_zoom_in = _make_button(_icon_zoom_in(c), self.tr("Acercar (Ctrl++)"))
        self._btn_zoom_out = _make_button(_icon_zoom_out(c), self.tr("Alejar (Ctrl+-)"))
        self._btn_zoom_fit = _make_button(
            _icon_zoom_fit(c),
            self.tr("Ajustar a p\u00e1gina (Ctrl+F)"),
        )
        self._btn_zoom_100 = _make_button(
            _icon_zoom_100(c),
            self.tr("Tamaño real (Ctrl+0)"),
        )

        layout.addWidget(self._btn_zoom_in)
        layout.addWidget(self._btn_zoom_out)
        layout.addWidget(self._btn_zoom_fit)
        layout.addWidget(self._btn_zoom_100)

        layout.addSpacing(6)
        layout.addWidget(self._separator())

        # --- Herramientas ---
        self._btn_rotate = _make_button(_icon_rotate(c), self.tr("Rotar 90° (Ctrl+R)"))
        self._btn_mark = _make_button(
            _icon_mark(c), self.tr("Marcar/desmarcar página (Ctrl+M)")
        )
        self._btn_delete_current = _make_button(
            _icon_delete_current(),
            self.tr("Eliminar página actual (Delete)"),
            obj_name="dangerButton",
        )
        self._btn_delete_from = _make_button(
            _icon_delete_from(),
            self.tr("Borrar desde aqu\u00ed"),
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
        self._btn_nav_script.clicked.connect(self.nav_script)
        self._btn_zoom_in.clicked.connect(self.zoom_in_requested)
        self._btn_zoom_out.clicked.connect(self.zoom_out_requested)
        self._btn_zoom_fit.clicked.connect(self.zoom_fit_requested)
        self._btn_zoom_100.clicked.connect(self.zoom_100_requested)
        self._btn_rotate.clicked.connect(self.rotate_requested)
        self._btn_mark.clicked.connect(self.mark_requested)
        self._btn_delete_current.clicked.connect(self.delete_current_requested)
        self._btn_delete_from.clicked.connect(self.delete_from_requested)
        self._edit_page.returnPressed.connect(self._on_page_entered)
        self._edit_page.textChanged.connect(lambda _t: self._fit_page_counter())
        self._edit_page.cancelled.connect(self._restore_page_number)

    # ------------------------------------------------------------------
    # Contador de página
    # ------------------------------------------------------------------

    def update_page_info(self, current: int, total: int) -> None:
        """Actualiza el indicador de página.

        Args:
            current: Página actual en base 1 (0 si el lote está vacío).
            total: Número total de páginas.
        """
        self._current_page = current
        self._total_pages = total
        self._edit_page.setText(str(current))
        self._edit_page.setEnabled(total > 0)
        self._lbl_page_info.setText(f"/ {total}")
        self._fit_page_counter()

    def _fit_page_counter(self) -> None:
        """Ajusta el contador «N / M» al ancho exacto de su texto.

        Con un ancho fijo, el número (alineado a la derecha) dejaba un hueco
        a su izquierda y el contador no quedaba centrado entre las flechas.
        El campo se ajusta a lo que contiene, también mientras se teclea.
        """
        self._edit_page.ensurePolished()
        self._lbl_page_info.ensurePolished()
        text = self._edit_page.text() or "0"
        self._edit_page.setFixedWidth(
            self._edit_page.fontMetrics().horizontalAdvance(text)
            + _COUNTER_EDIT_CHROME
        )
        self._lbl_page_info.setFixedWidth(
            self._lbl_page_info.fontMetrics().horizontalAdvance(
                self._lbl_page_info.text()
            )
        )

    def changeEvent(self, event) -> None:  # noqa: N802 — API de Qt
        """Reajusta el contador si cambia la fuente (tema o A+/A−)."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit_page_counter()

    def is_editing_page(self) -> bool:
        """¿El usuario está tecleando en el contador de página?

        El workbench lo consulta para no disparar atajos de tecla simple
        (flechas, Inicio/Fin, Supr) mientras se escribe un número.
        """
        return self._edit_page.hasFocus()

    def _on_page_entered(self) -> None:
        """Valida lo tecleado y pide el salto si procede."""
        text = self._edit_page.text().strip()
        self._edit_page.clearFocus()

        if not text.isdigit() or self._total_pages <= 0:
            self._restore_page_number()
            return

        number = int(text)
        if number < 1 or number > self._total_pages:
            log.debug(
                "Página %d fuera de rango (1-%d), se ignora",
                number,
                self._total_pages,
            )
            self._restore_page_number()
            return

        self.page_jump_requested.emit(number - 1)

    def _restore_page_number(self) -> None:
        """Devuelve el campo al valor de la página realmente mostrada."""
        self._edit_page.setText(str(self._current_page))

    def update_icon_color(self, color: str) -> None:
        """Regenera los iconos con un color nuevo (al cambiar tema)."""
        self._btn_first.setIcon(_icon_first(color))
        self._btn_prev.setIcon(_icon_prev(color))
        self._btn_next.setIcon(_icon_next(color))
        self._btn_last.setIcon(_icon_last(color))
        self._btn_next_bc.setIcon(_icon_next_barcode(color))
        self._btn_next_review.setIcon(_icon_next_review(color))
        self._btn_nav_script.setIcon(_icon_nav_script(color))
        self._btn_zoom_in.setIcon(_icon_zoom_in(color))
        self._btn_zoom_out.setIcon(_icon_zoom_out(color))
        self._btn_zoom_fit.setIcon(_icon_zoom_fit(color))
        self._btn_zoom_100.setIcon(_icon_zoom_100(color))
        self._btn_rotate.setIcon(_icon_rotate(color))
        self._btn_mark.setIcon(_icon_mark(color))
        self._btn_delete_current.setIcon(_icon_delete_current())
        self._btn_delete_from.setIcon(_icon_delete_from())

    def _separator(self) -> QWidget:
        """Crea un separador vertical delgado."""
        sep = QWidget()
        sep.setFixedSize(1, 28)
        sep.setObjectName("overlaySeparator")
        return sep
