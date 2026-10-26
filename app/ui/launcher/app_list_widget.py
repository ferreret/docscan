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
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QRectF, QSize, Qt, Signal
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

# Medidas de Flexibar (px a 13 px de letra)
BASE_FONT_PX = 13
CARD_HEIGHT = 88
CARD_GAP = 8
INDICATOR_WIDTH = 4
TILE_SIZE = 48
TILE_MARGIN = 16
KEBAB_SIZE = 32
KEBAB_MARGIN = 10


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


class AppCardDelegate(QStyledItemDelegate):
    """Dibuja cada aplicación como una tarjeta."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
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

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        s = _scale(option.font)
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

    def populate(self, apps: list[Any]) -> None:
        """Llena la lista con objetos Application del ORM."""
        self.clear()
        for app in apps:
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
                },
            )
            if not app.active:
                item.setToolTip(
                    QCoreApplication.translate("AppListWidget", "Aplicación inactiva")
                )
            self.addItem(item)

    def kebab_rect_for(self, item: QListWidgetItem) -> QRect:
        """Zona del botón ⋮ de ``item``, en coordenadas del viewport."""
        return kebab_rect(self.visualItemRect(item), _scale(self.font()))

    def mousePressEvent(self, event) -> None:  # noqa: N802 — API de Qt
        item = self.itemAt(event.position().toPoint())
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

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.pos())
        if item is None:
            return
        self.setCurrentItem(item)
        self.menu_requested.emit(event.globalPos())

    def filter_apps(self, text: str) -> None:
        """Filtra los items visibles por nombre."""
        text_lower = text.lower()
        for i in range(self.count()):
            item = self.item(i)
            item.setHidden(text_lower not in item.text().lower())

    def selected_app_id(self) -> int | None:
        """Devuelve el ID de la aplicación seleccionada, o None."""
        item = self.currentItem()
        if item is None:
            return None
        return item.data(APP_ID_ROLE)

    def selected_app_name(self) -> str | None:
        """Devuelve el nombre de la aplicación seleccionada."""
        item = self.currentItem()
        if item is None:
            return None
        return item.text()

    def selected_app_data(self) -> dict | None:
        """Devuelve todos los datos de la aplicación seleccionada."""
        item = self.currentItem()
        if item is None:
            return None
        return item.data(APP_DATA_ROLE)
