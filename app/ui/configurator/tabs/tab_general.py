"""Pestaña General del configurador de aplicación."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.services.scanner_service import get_available_backends


class GeneralTab(QWidget):
    """Pestaña de configuración general de la aplicación."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui(app)

    def _setup_ui(self, app: Application) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Grupo principal ---
        main_form = QFormLayout()
        main_form.setVerticalSpacing(10)
        main_form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit(app.name)
        main_form.addRow("Nombre:", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(app.description)
        self._desc_edit.setMaximumHeight(80)
        main_form.addRow("Descripción:", self._desc_edit)

        self._active_check = QCheckBox("Activa")
        self._active_check.setChecked(app.active)
        main_form.addRow("", self._active_check)

        self._scanner_combo = QComboBox()
        self._scanner_combo.addItems(get_available_backends() or ["sane", "twain", "wia"])
        idx = self._scanner_combo.findText(app.scanner_backend)
        if idx >= 0:
            self._scanner_combo.setCurrentIndex(idx)
        main_form.addRow("Backend escáner:", self._scanner_combo)

        self._auto_transfer = QCheckBox("Transferir automáticamente")
        self._auto_transfer.setChecked(app.auto_transfer)
        main_form.addRow("", self._auto_transfer)

        self._close_after = QCheckBox("Cerrar tras transferir")
        self._close_after.setChecked(app.close_after_transfer)
        main_form.addRow("", self._close_after)

        layout.addLayout(main_form)

        # --- Grupo: Barcode manual ---
        bc_group = QGroupBox("Barcode manual")
        bc_form = QFormLayout(bc_group)
        bc_form.setVerticalSpacing(10)
        bc_form.setContentsMargins(12, 16, 12, 12)

        self._bc_regex_edit = QLineEdit()
        self._bc_regex_edit.setPlaceholderText(
            r"Ej: ^\d{8}$ (vacío = sin validación)"
        )
        self._bc_regex_edit.setToolTip(
            "Expresión regular para validar el código de barras\n"
            "introducido manualmente. Dejar vacío para no validar."
        )
        bc_form.addRow("Validación (regex):", self._bc_regex_edit)

        self._bc_fixed_edit = QLineEdit()
        self._bc_fixed_edit.setPlaceholderText("Vacío = solicitar valor al usuario")
        self._bc_fixed_edit.setToolTip(
            "Valor fijo que se inserta al pulsar '+ Barcode manual'.\n"
            "Si está vacío, se solicita el valor al usuario."
        )
        bc_form.addRow("Valor fijo:", self._bc_fixed_edit)

        layout.addWidget(bc_group)

        # Cargar configuración de barcode manual
        self._load_barcode_config(app)

        layout.addStretch()

    @staticmethod
    def _parse_ai_config(app: Application) -> dict:
        """Parsea ai_config_json con fallback a dict vacío."""
        try:
            return json.loads(app.ai_config_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def _load_barcode_config(self, app: Application) -> None:
        """Carga configuración de barcode manual desde ai_config_json."""
        config = self._parse_ai_config(app)
        self._bc_regex_edit.setText(config.get("barcode_regex", ""))
        self._bc_fixed_edit.setText(config.get("barcode_fixed_value", ""))

    def apply_to(self, app: Application) -> None:
        """Aplica los valores del formulario al objeto Application."""
        app.name = self._name_edit.text().strip()
        app.description = self._desc_edit.toPlainText().strip()
        app.active = self._active_check.isChecked()
        app.scanner_backend = self._scanner_combo.currentText()
        app.auto_transfer = self._auto_transfer.isChecked()
        app.close_after_transfer = self._close_after.isChecked()

        config = self._parse_ai_config(app)
        config["barcode_regex"] = self._bc_regex_edit.text().strip()
        config["barcode_fixed_value"] = self._bc_fixed_edit.text().strip()
        app.ai_config_json = json.dumps(config, ensure_ascii=False)
