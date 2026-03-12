"""Widget de lista de aplicaciones con cards visuales."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
)

from app.ui.theme_manager import ThemeManager

# Roles personalizados para almacenar datos en cada item
APP_ID_ROLE = Qt.ItemDataRole.UserRole
APP_DATA_ROLE = Qt.ItemDataRole.UserRole + 1

# Dimensiones de la card
CARD_HEIGHT = 72
CARD_MARGIN = 4
INDICATOR_WIDTH = 4
AVATAR_SIZE = 40
AVATAR_MARGIN_LEFT = 16
TEXT_MARGIN_LEFT = AVATAR_MARGIN_LEFT + AVATAR_SIZE + 14


class AppCardDelegate(QStyledItemDelegate):
    """Delegate que dibuja cada aplicación como una card visual."""

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        app_data = index.data(APP_DATA_ROLE)
        if not app_data:
            painter.restore()
            return

        is_active = app_data.get("active", True)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_dark = ThemeManager().is_dark

        # --- Colores según tema ---
        if is_dark:
            bg_color = QColor("#45475a") if is_selected else QColor("#313244")
            if is_hovered and not is_selected:
                bg_color = QColor("#3b3d52")
            text_color = QColor("#cdd6f4")
            subtext_color = QColor("#a6adc8")
            date_color = QColor("#6c7086")
            avatar_bg = QColor("#585b70")
            avatar_text = QColor("#cdd6f4")
            active_color = QColor("#a6e3a1")
            inactive_color = QColor("#585b70")
            selected_border = QColor("#89b4fa")
        else:
            bg_color = QColor("#e8ecf5") if is_selected else QColor("#ffffff")
            if is_hovered and not is_selected:
                bg_color = QColor("#f4f5fa")
            text_color = QColor("#4c4f69")
            subtext_color = QColor("#6c6f85")
            date_color = QColor("#9ca0b0")
            avatar_bg = QColor("#dce0e8")
            avatar_text = QColor("#4c4f69")
            active_color = QColor("#40a02b")
            inactive_color = QColor("#bcc0cc")
            selected_border = QColor("#1e66f5")

        # --- Fondo de la card (el QSS ya pinta el item, pero dibujamos encima) ---
        card_rect = rect.adjusted(2, 2, -2, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(card_rect, 8, 8)

        # Borde en selección
        if is_selected:
            painter.setPen(QPen(selected_border, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(card_rect, 8, 8)

        # --- Indicador de estado (barra lateral izquierda) ---
        indicator_color = active_color if is_active else inactive_color
        indicator_rect = QRect(
            card_rect.left() + 1, card_rect.top() + 12,
            INDICATOR_WIDTH, card_rect.height() - 24,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(indicator_color))
        painter.drawRoundedRect(indicator_rect, 2, 2)

        # --- Avatar circular con la primera letra ---
        name = app_data.get("name", "?")
        avatar_x = card_rect.left() + AVATAR_MARGIN_LEFT
        avatar_y = card_rect.top() + (card_rect.height() - AVATAR_SIZE) // 2
        avatar_rect = QRect(avatar_x, avatar_y, AVATAR_SIZE, AVATAR_SIZE)

        painter.setBrush(QBrush(avatar_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(avatar_rect)

        avatar_font = QFont(painter.font())
        avatar_font.setPointSize(15)
        avatar_font.setWeight(QFont.Weight.Bold)
        painter.setFont(avatar_font)
        painter.setPen(avatar_text)
        painter.drawText(avatar_rect, Qt.AlignmentFlag.AlignCenter, name[0].upper())

        # --- Texto: nombre ---
        text_x = card_rect.left() + TEXT_MARGIN_LEFT
        text_width = card_rect.width() - TEXT_MARGIN_LEFT - 120  # espacio para fecha

        name_font = QFont(painter.font())
        name_font.setPointSize(11)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(text_color if is_active else subtext_color)
        name_rect = QRect(text_x, card_rect.top() + 12, text_width, 22)
        painter.drawText(
            name_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            name,
        )

        # --- Texto: descripción ---
        description = app_data.get("description", "")
        if description:
            desc_font = QFont(painter.font())
            desc_font.setPointSize(9)
            desc_font.setWeight(QFont.Weight.Normal)
            painter.setFont(desc_font)
            painter.setPen(subtext_color)
            desc_rect = QRect(text_x, card_rect.top() + 34, text_width, 20)
            # Truncar descripción si es muy larga
            metrics = painter.fontMetrics()
            elided = metrics.elidedText(
                description, Qt.TextElideMode.ElideRight, text_width,
            )
            painter.drawText(
                desc_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )

        # --- Fecha de creación (esquina derecha) ---
        created_at = app_data.get("created_at", "")
        if created_at:
            date_font = QFont(painter.font())
            date_font.setPointSize(8)
            painter.setFont(date_font)
            painter.setPen(date_color)
            date_text = created_at[:10] if len(created_at) >= 10 else created_at
            date_rect = QRect(
                card_rect.right() - 110, card_rect.top() + 12,
                100, 20,
            )
            painter.drawText(
                date_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                date_text,
            )

        # --- Badge estado (activa/inactiva) ---
        if not is_active:
            badge_font = QFont(painter.font())
            badge_font.setPointSize(8)
            painter.setFont(badge_font)
            painter.setPen(inactive_color)
            badge_rect = QRect(
                card_rect.right() - 110, card_rect.top() + 36,
                100, 18,
            )
            painter.drawText(
                badge_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Inactiva",
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), CARD_HEIGHT + CARD_MARGIN)


class AppListWidget(QListWidget):
    """Lista de aplicaciones con filtro por nombre y visualización en cards."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setItemDelegate(AppCardDelegate(self))
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.setSpacing(2)

    def populate(self, apps: list[Any]) -> None:
        """Llena la lista con objetos Application del ORM."""
        self.clear()
        for app in apps:
            item = QListWidgetItem()
            item.setText(app.name)
            item.setData(APP_ID_ROLE, app.id)
            item.setData(APP_DATA_ROLE, {
                "name": app.name,
                "description": app.description or "",
                "active": app.active,
                "created_at": str(app.created_at) if app.created_at else "",
            })
            item.setSizeHint(QSize(0, CARD_HEIGHT + CARD_MARGIN))
            self.addItem(item)

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
