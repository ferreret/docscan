"""Lista de aplicaciones del launcher con tarjetas como las de FlexibarNET 10.

Cada tarjeta lleva, de izquierda a derecha:
- el indicador de estado (verde si está activa);
- el icono sobre su acento;
- el nombre, la descripción y hasta tres etiquetas;
- la fecha de la última modificación;
- el botón ⋮ con el menú de acciones.

El icono, el acento y las etiquetas se derivan de la configuración
(``app/ui/launcher/app_card.py``). Las medidas son las de Flexibar a 13 px y
escalan con el tamaño de letra elegido (A+/A−).

Grupos (FlexibarNET10 ``App.Group``): las aplicaciones sin grupo van primero,
en el nivel raíz y sin cabecera; después, cada grupo en orden alfabético bajo
una cabecera plegable con su nombre y el número de aplicaciones. El plegado
se recuerda por equipo.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QCoreApplication,
    QPoint,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QFontInfo, QPainter, QPen
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from app.ui.icons import svg_icon
from app.ui.launcher.app_card import AppCardInfo, card_info
from app.ui.palette import color

# Roles personalizados para almacenar datos en cada item
APP_ID_ROLE = Qt.ItemDataRole.UserRole
APP_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
GROUP_ROLE = Qt.ItemDataRole.UserRole + 2  # nombre del grupo, en las cabeceras
GROUP_COUNT_ROLE = Qt.ItemDataRole.UserRole + 3
GROUP_COLLAPSED_ROLE = Qt.ItemDataRole.UserRole + 4

# Grupos plegados, por equipo (como LauncherGroupCollapsed en Flexibar)
COLLAPSED_GROUPS_KEY = "launcher/collapsed_groups"

# Medidas de Flexibar (px a 13 px de letra)
BASE_FONT_PX = 13
CARD_HEIGHT = 88
CARD_GAP = 8
INDICATOR_WIDTH = 4
TILE_SIZE = 48
TILE_MARGIN = 16
KEBAB_SIZE = 32
KEBAB_MARGIN = 10
GROUP_HEADER_HEIGHT = 40
GROUP_TOP_GAP = 4


def _scale(font: QFont) -> float:
    """Factor respecto a los 13 px de referencia (sigue a A+/A−)."""
    px = QFontInfo(font).pixelSize() or BASE_FONT_PX
    return max(0.75, px / BASE_FONT_PX)


def card_rect(item_rect: QRect) -> QRect:
    """Rectángulo de la tarjeta dentro del item (sin el hueco inferior)."""
    return item_rect.adjusted(2, 0, -2, -CARD_GAP)


def kebab_rect(item_rect: QRect, scale: float = 1.0) -> QRect:
    """Zona del botón ⋮ de la tarjeta."""
    card = card_rect(item_rect)
    size = round(KEBAB_SIZE * scale)
    return QRect(
        card.right() - round(KEBAB_MARGIN * scale) - size,
        card.center().y() - size // 2,
        size,
        size,
    )


def _group_sort_key(app: Any) -> tuple[int, str]:
    """Sin grupo primero; después los grupos en orden alfabético."""
    group = (getattr(app, "group", "") or "").strip()
    return (1 if group else 0, group.casefold())


def _load_collapsed_groups() -> set[str]:
    value = QSettings("DocScanStudio", "DocScanStudio").value(COLLAPSED_GROUPS_KEY, [])
    if isinstance(value, str):  # QSettings devuelve str si solo hay uno
        value = [value]
    return {g for g in value or [] if isinstance(g, str) and g}


def _save_collapsed_groups(groups: set[str]) -> None:
    QSettings("DocScanStudio", "DocScanStudio").setValue(
        COLLAPSED_GROUPS_KEY, sorted(groups)
    )


class AppCardDelegate(QStyledItemDelegate):
    """Dibuja cada aplicación como una tarjeta y cada grupo como su cabecera."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        if index.data(GROUP_ROLE):
            self._paint_group_header(painter, option, index)
            return
        app_data = index.data(APP_DATA_ROLE)
        if not app_data:
            return
        info: AppCardInfo = app_data["card"]
        s = _scale(option.font)

        def px(value: float) -> int:
            return round(value * s)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_active = app_data.get("active", True)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # --- Fondo y borde ---
        card = card_rect(option.rect)
        bg = color("surface1") if is_selected else color("surface0")
        if is_hovered and not is_selected:
            bg = color("hover")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(bg)))
        painter.drawRoundedRect(QRectF(card), 10, 10)
        if is_selected:
            painter.setPen(QPen(QColor(color("blue")), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(card).adjusted(0.75, 0.75, -0.75, -0.75), 10, 10
            )

        # --- Indicador de estado ---
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color("green") if is_active else color("surface2")))
        painter.drawRoundedRect(
            QRectF(card.left(), card.top() + 12, INDICATOR_WIDTH, card.height() - 24),
            2,
            2,
        )

        # --- Icono sobre su acento ---
        tile = px(TILE_SIZE)
        tile_rect = QRect(
            card.left() + INDICATOR_WIDTH + px(TILE_MARGIN),
            card.center().y() - tile // 2,
            tile,
            tile,
        )
        painter.setBrush(QColor(color(info.accent)))
        painter.drawRoundedRect(QRectF(tile_rect), px(12), px(12))
        glyph = px(22)
        svg_icon(info.icon_name, "#ffffff", glyph, stroke=2.0).paint(
            painter,
            QRect(
                tile_rect.center().x() - glyph // 2 + 1,
                tile_rect.center().y() - glyph // 2 + 1,
                glyph,
                glyph,
            ),
        )

        # --- Columna derecha: ⋮ y fecha ---
        kebab = kebab_rect(option.rect, s)
        dots = px(16)
        svg_icon("ellipsis-vertical", color("subtext0"), dots).paint(
            painter,
            QRect(
                kebab.center().x() - dots // 2 + 1,
                kebab.center().y() - dots // 2 + 1,
                dots,
                dots,
            ),
        )
        right_edge = kebab.left() - px(4)
        if info.updated:
            date_font = QFont(option.font)
            date_font.setPixelSize(px(11.5))
            painter.setFont(date_font)
            date_w = painter.fontMetrics().horizontalAdvance(info.updated)
            date_rect = QRect(right_edge - date_w, card.top(), date_w, card.height())
            painter.setPen(QColor(color("subtext0")))
            painter.drawText(date_rect, Qt.AlignmentFlag.AlignVCenter, info.updated)
            cal = px(13)
            svg_icon("calendar", color("overlay0"), cal).paint(
                painter,
                QRect(
                    date_rect.left() - px(6) - cal,
                    card.center().y() - cal // 2,
                    cal,
                    cal,
                ),
            )
            right_edge = date_rect.left() - px(6) - cal - px(16)

        # --- Texto: nombre, descripción y etiquetas ---
        x = tile_rect.right() + px(TILE_MARGIN) + 1
        width = max(40, right_edge - x)

        name_font = QFont(option.font)
        name_font.setPixelSize(px(15))
        name_font.setWeight(QFont.Weight.DemiBold)
        desc_font = QFont(option.font)
        desc_font.setPixelSize(px(11.5))
        tag_font = QFont(option.font)
        tag_font.setPixelSize(px(10.5))

        description = app_data.get("description", "")
        painter.setFont(name_font)
        name_h = painter.fontMetrics().height()
        painter.setFont(desc_font)
        desc_h = painter.fontMetrics().height() if description else 0
        painter.setFont(tag_font)
        tag_h = painter.fontMetrics().height() + px(4)
        block_h = name_h + (px(3) + desc_h if description else 0) + px(7) + tag_h
        y = card.center().y() - block_h // 2

        painter.setFont(name_font)
        painter.setPen(QColor(color("text") if is_active else color("subtext0")))
        name = painter.fontMetrics().elidedText(
            app_data.get("name", ""), Qt.TextElideMode.ElideRight, width
        )
        painter.drawText(
            QRect(x, y, width, name_h), Qt.AlignmentFlag.AlignVCenter, name
        )
        y += name_h

        if description:
            y += px(3)
            painter.setFont(desc_font)
            painter.setPen(QColor(color("overlay0")))
            desc = painter.fontMetrics().elidedText(
                description, Qt.TextElideMode.ElideRight, width
            )
            painter.drawText(
                QRect(x, y, width, desc_h), Qt.AlignmentFlag.AlignVCenter, desc
            )
            y += desc_h

        y += px(7)
        painter.setFont(tag_font)
        metrics = painter.fontMetrics()
        tag_x = x
        for tag in info.tags:
            chip_w = metrics.horizontalAdvance(tag) + px(14)
            if tag_x + chip_w > x + width:
                break
            chip = QRect(tag_x, y, chip_w, tag_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color("surface1")))
            painter.drawRoundedRect(QRectF(chip), 4, 4)
            painter.setPen(QColor(color("blue")))
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, tag)
            tag_x += chip_w + px(6)

        painter.restore()

    def _paint_group_header(
        self, painter: QPainter, option: QStyleOptionViewItem, index
    ) -> None:
        """Banda de la cabecera: acento, chevron, nombre y contador.

        Misma gramática visual que las tarjetas, como la cabecera de Flexibar.
        """
        s = _scale(option.font)

        def px(value: float) -> int:
            return round(value * s)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        band = option.rect.adjusted(2, GROUP_TOP_GAP, -2, -CARD_GAP)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.setBrush(QColor(color("surface1")))
        border = color("blue") if is_hovered else color("surface2")
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(QRectF(band).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        # Acento azul a la izquierda, recortado a la esquina redondeada
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color("blue")))
        painter.setClipRect(
            QRect(band.left(), band.top(), INDICATOR_WIDTH, band.height())
        )
        painter.drawRoundedRect(QRectF(band), 8, 8)
        painter.setClipping(False)

        collapsed = bool(index.data(GROUP_COLLAPSED_ROLE))
        chevron = px(14)
        x = band.left() + INDICATOR_WIDTH + px(10)
        svg_icon(
            "chevron-right" if collapsed else "chevron-down", color("blue"), chevron
        ).paint(
            painter,
            QRect(x, band.center().y() - chevron // 2 + 1, chevron, chevron),
        )
        x += chevron + px(10)

        count = str(index.data(GROUP_COUNT_ROLE) or 0)
        badge_font = QFont(option.font)
        badge_font.setPixelSize(px(11))
        badge_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(badge_font)
        badge_w = painter.fontMetrics().horizontalAdvance(count) + px(16)
        badge_h = painter.fontMetrics().height() + px(4)

        name_font = QFont(option.font)
        name_font.setPixelSize(px(15))
        name_font.setWeight(QFont.Weight.Bold)
        painter.setFont(name_font)
        max_w = max(40, band.right() - px(12) - badge_w - px(10) - x)
        name = painter.fontMetrics().elidedText(
            str(index.data(GROUP_ROLE)), Qt.TextElideMode.ElideRight, max_w
        )
        name_w = painter.fontMetrics().horizontalAdvance(name)
        painter.setPen(QColor(color("text")))
        painter.drawText(
            QRect(x, band.top(), name_w, band.height()),
            Qt.AlignmentFlag.AlignVCenter,
            name,
        )
        x += name_w + px(10)

        badge = QRect(x, band.center().y() - badge_h // 2, badge_w, badge_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color("surface2")))
        painter.drawRoundedRect(QRectF(badge), 4, 4)
        painter.setFont(badge_font)
        painter.setPen(QColor(color("text")))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, count)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        s = _scale(option.font)
        if index is not None and index.data(GROUP_ROLE):
            height = round(GROUP_HEADER_HEIGHT * s) + GROUP_TOP_GAP + CARD_GAP
            return QSize(option.rect.width(), height)
        return QSize(option.rect.width(), round(CARD_HEIGHT * s) + CARD_GAP)


class AppListWidget(QListWidget):
    """Lista de aplicaciones con filtro por nombre y tarjetas.

    Signals:
        menu_requested: El usuario pide el menú de acciones de una tarjeta,
            con el botón ⋮ o con el botón derecho (posición global del menú).
    """

    menu_requested = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appList")
        self.setItemDelegate(AppCardDelegate(self))
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.setSpacing(0)
        self._filter_text = ""
        self._collapsed = _load_collapsed_groups()

    def populate(self, apps: list[Any]) -> None:
        """Llena la lista con objetos Application del ORM.

        Las aplicaciones sin grupo van primero y sin cabecera; los grupos,
        después y en orden alfabético. Dentro de cada bloque se conserva el
        orden recibido.
        """
        self.clear()
        current_group = ""
        for app in sorted(apps, key=_group_sort_key):
            group = (getattr(app, "group", "") or "").strip()
            if group and group != current_group:
                self.addItem(self._make_header(group))
                current_group = group
            item = QListWidgetItem()
            item.setText(app.name)
            item.setData(APP_ID_ROLE, app.id)
            item.setData(
                APP_DATA_ROLE,
                {
                    "name": app.name,
                    "description": app.description or "",
                    "active": app.active,
                    "created_at": str(app.created_at) if app.created_at else "",
                    "card": card_info(app),
                    "group": group,
                },
            )
            if not app.active:
                item.setToolTip(
                    QCoreApplication.translate("AppListWidget", "Aplicación inactiva")
                )
            self.addItem(item)
        self._refresh_visibility()

    def _make_header(self, group: str) -> QListWidgetItem:
        """Cabecera de ``group``: no se selecciona, se pliega con un clic."""
        item = QListWidgetItem()
        item.setText(group)
        item.setData(GROUP_ROLE, group)
        item.setData(GROUP_COLLAPSED_ROLE, group in self._collapsed)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setToolTip(
            QCoreApplication.translate(
                "AppListWidget", "Clic para plegar o desplegar el grupo"
            )
        )
        return item

    @staticmethod
    def is_group_header(item: QListWidgetItem | None) -> bool:
        """True si ``item`` es la cabecera de un grupo."""
        return item is not None and bool(item.data(GROUP_ROLE))

    def app_count(self) -> int:
        """Número de aplicaciones (sin contar las cabeceras de grupo)."""
        return sum(
            1 for i in range(self.count()) if not self.is_group_header(self.item(i))
        )

    def group_names(self) -> list[str]:
        """Grupos con cabecera, en el orden de la lista."""
        return [
            self.item(i).data(GROUP_ROLE)
            for i in range(self.count())
            if self.is_group_header(self.item(i))
        ]

    def is_group_collapsed(self, group: str) -> bool:
        return group in self._collapsed

    def set_group_collapsed(self, group: str, collapsed: bool) -> None:
        """Pliega o despliega ``group`` y lo recuerda."""
        if collapsed:
            self._collapsed.add(group)
        else:
            self._collapsed.discard(group)
        _save_collapsed_groups(self._collapsed)
        for i in range(self.count()):
            item = self.item(i)
            if item.data(GROUP_ROLE) == group:
                item.setData(GROUP_COLLAPSED_ROLE, collapsed)
        current = self.currentItem()
        if collapsed and current is not None and not self.is_group_header(current):
            if (current.data(APP_DATA_ROLE) or {}).get("group") == group:
                self.setCurrentRow(-1)
        self._refresh_visibility()

    def toggle_group(self, group: str) -> None:
        self.set_group_collapsed(group, not self.is_group_collapsed(group))

    def _refresh_visibility(self) -> None:
        """Aplica el filtro de búsqueda y el plegado de los grupos.

        Como en Flexibar, la cabecera cuenta las aplicaciones que pasan el
        filtro y desaparece si no queda ninguna; un grupo plegado sigue
        plegado mientras se busca.
        """
        text = self._filter_text.lower()
        header: QListWidgetItem | None = None
        matches = 0

        def close_header() -> None:
            if header is not None:
                header.setData(GROUP_COUNT_ROLE, matches)
                header.setHidden(matches == 0)

        for i in range(self.count()):
            item = self.item(i)
            if self.is_group_header(item):
                close_header()
                header, matches = item, 0
                continue
            match = text in item.text().lower()
            if match and header is not None:
                matches += 1
            collapsed = header is not None and self.is_group_collapsed(
                header.data(GROUP_ROLE)
            )
            item.setHidden(not match or collapsed)
        close_header()

    def kebab_rect_for(self, item: QListWidgetItem) -> QRect:
        """Zona del botón ⋮ de ``item``, en coordenadas del viewport."""
        return kebab_rect(self.visualItemRect(item), _scale(self.font()))

    def mousePressEvent(self, event) -> None:  # noqa: N802 — API de Qt
        item = self.itemAt(event.position().toPoint())
        if self.is_group_header(item):
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_group(item.data(GROUP_ROLE))
            return
        if (
            item is not None
            and event.button() == Qt.MouseButton.LeftButton
            and self.kebab_rect_for(item).contains(event.position().toPoint())
        ):
            self.setCurrentItem(item)
            rect = self.kebab_rect_for(item)
            self.menu_requested.emit(self.viewport().mapToGlobal(rect.bottomLeft()))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        # La cabecera es un botón: mano encima, como en Flexibar
        if self.is_group_header(self.itemAt(event.position().toPoint())):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        # Doble clic en una cabecera = dos clics (pliega y despliega), y no
        # debe abrir ninguna aplicación.
        item = self.itemAt(event.position().toPoint())
        if self.is_group_header(item):
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_group(item.data(GROUP_ROLE))
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.pos())
        if item is None or self.is_group_header(item):
            return
        self.setCurrentItem(item)
        self.menu_requested.emit(event.globalPos())

    def filter_apps(self, text: str) -> None:
        """Filtra los items visibles por nombre."""
        self._filter_text = text
        self._refresh_visibility()

    def selected_app_id(self) -> int | None:
        """Devuelve el ID de la aplicación seleccionada, o None."""
        item = self.currentItem()
        if item is None:
            return None
        return item.data(APP_ID_ROLE)

    def selected_app_name(self) -> str | None:
        """Devuelve el nombre de la aplicación seleccionada."""
        item = self.currentItem()
        if item is None or self.is_group_header(item):
            return None
        return item.text()

    def selected_app_data(self) -> dict | None:
        """Devuelve todos los datos de la aplicación seleccionada."""
        item = self.currentItem()
        if item is None or self.is_group_header(item):
            return None
        return item.data(APP_DATA_ROLE)
