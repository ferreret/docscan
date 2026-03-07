"""Widget de lista de aplicaciones para el launcher."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem


# Roles personalizados para almacenar datos en cada item
APP_ID_ROLE = Qt.ItemDataRole.UserRole
APP_DATA_ROLE = Qt.ItemDataRole.UserRole + 1


class AppListWidget(QListWidget):
    """Lista de aplicaciones con filtro por nombre."""

    def populate(self, apps: list[Any]) -> None:
        """Llena la lista con objetos Application del ORM.

        Args:
            apps: Lista de objetos Application.
        """
        self.clear()
        for app in apps:
            item = QListWidgetItem()
            item.setText(app.name)
            item.setData(APP_ID_ROLE, app.id)
            item.setData(APP_DATA_ROLE, {
                "name": app.name,
                "description": app.description,
                "active": app.active,
                "created_at": str(app.created_at) if app.created_at else "",
            })

            if not app.active:
                item.setForeground(Qt.GlobalColor.gray)

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
