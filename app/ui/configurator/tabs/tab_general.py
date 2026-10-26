"""Pestaña General del configurador de aplicación."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.models.workbench_layout import (
    BARCODES,
    CAMPOS,
    LOG,
    OCR,
    PANEL_IDS,
    VERIFICACION,
    LayoutEntry,
    WorkbenchLayout,
)
from app.services.scanner_service import get_available_backends


class GeneralTab(QWidget):
    """Pestaña de configuración general de la aplicación."""

    def __init__(self, app: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui(app)

    def _setup_ui(self, app: Application) -> None:
        # Con scroll: la pestaña ya no cabe a la altura del diálogo y, sin él,
        # Qt aplastaba los campos (Nombre, Descripción) y la lista de pestañas.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Grupo principal ---
        main_form = QFormLayout()
        main_form.setVerticalSpacing(10)
        main_form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit(app.name)
        main_form.addRow(self.tr("Nombre:"), self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(app.description)
        self._desc_edit.setMaximumHeight(80)
        main_form.addRow(self.tr("Descripción:"), self._desc_edit)

        self._active_check = QCheckBox(self.tr("Activa"))
        self._active_check.setChecked(app.active)
        main_form.addRow("", self._active_check)

        self._scanner_combo = QComboBox()
        self._scanner_combo.addItems(
            get_available_backends() or ["sane", "twain", "wia"]
        )
        idx = self._scanner_combo.findText(app.scanner_backend)
        if idx >= 0:
            self._scanner_combo.setCurrentIndex(idx)
        main_form.addRow(self.tr("Backend escáner:"), self._scanner_combo)

        self._auto_transfer = QCheckBox(self.tr("Transferir automáticamente"))
        self._auto_transfer.setChecked(app.auto_transfer)
        main_form.addRow("", self._auto_transfer)

        self._close_after = QCheckBox(self.tr("Cerrar tras transferir"))
        self._close_after.setChecked(app.close_after_transfer)
        main_form.addRow("", self._close_after)

        layout.addLayout(main_form)

        # --- Grupo: Barcode manual ---
        bc_group = QGroupBox(self.tr("Barcode manual"))
        bc_form = QFormLayout(bc_group)
        bc_form.setVerticalSpacing(10)
        bc_form.setContentsMargins(12, 16, 12, 12)

        self._bc_regex_edit = QLineEdit()
        self._bc_regex_edit.setPlaceholderText(
            self.tr(r"Ej: ^\d{8}$ (vacío = sin validación)")
        )
        self._bc_regex_edit.setToolTip(
            self.tr(
                "Expresión regular para validar el código de barras\n"
                "introducido manualmente. Dejar vacío para no validar."
            )
        )
        bc_form.addRow(self.tr("Validación (regex):"), self._bc_regex_edit)

        self._bc_fixed_edit = QLineEdit()
        self._bc_fixed_edit.setPlaceholderText(
            self.tr("Vacío = solicitar valor al usuario")
        )
        self._bc_fixed_edit.setToolTip(
            self.tr(
                "Valor fijo que se inserta al pulsar '+ Barcode manual'.\n"
                "Si está vacío, se solicita el valor al usuario."
            )
        )
        bc_form.addRow(self.tr("Valor fijo:"), self._bc_fixed_edit)

        self._hide_add_barcode = QCheckBox(
            self.tr("Ocultar el botón «+ Añadir» en el Workbench")
        )
        self._hide_add_barcode.setToolTip(
            self.tr(
                "Oculta el botón y desactiva también sus atajos (Ctrl+N, Insert).\n"
                "La lectura de códigos del pipeline no cambia."
            )
        )
        self._hide_add_barcode.setChecked(
            bool(getattr(app, "hide_add_barcode_button", False))
        )
        bc_form.addRow("", self._hide_add_barcode)

        layout.addWidget(bc_group)

        layout.addWidget(self._build_workbench_layout_group(app))

        # --- Grupo: Detección de páginas en blanco ---
        blank_group = QGroupBox(self.tr("Detección de páginas en blanco"))
        blank_form = QFormLayout(blank_group)
        blank_form.setVerticalSpacing(10)
        blank_form.setContentsMargins(12, 16, 12, 12)

        self._blank_enabled = QCheckBox(self.tr("Detectar páginas en blanco"))
        self._blank_enabled.setToolTip(
            self.tr(
                "Analiza cada página tras el pipeline y marca como\n"
                "en blanco si el contenido está por debajo del umbral."
            )
        )
        self._blank_enabled.toggled.connect(self._on_blank_enabled_changed)
        blank_form.addRow("", self._blank_enabled)

        self._blank_threshold = QDoubleSpinBox()
        self._blank_threshold.setRange(0.1, 20.0)
        self._blank_threshold.setValue(1.0)
        self._blank_threshold.setSingleStep(0.5)
        self._blank_threshold.setSuffix(" %")
        self._blank_threshold.setToolTip(
            self.tr(
                "Porcentaje mínimo de contenido para NO considerar\n"
                "la página como en blanco. Ejemplo: 1.0 = si menos\n"
                "del 1% de píxeles tienen contenido, es una página\n"
                "en blanco."
            )
        )
        self._blank_threshold_label = self.tr("Umbral de contenido:")
        blank_form.addRow(self._blank_threshold_label, self._blank_threshold)

        self._blank_tolerance = QSpinBox()
        self._blank_tolerance.setRange(200, 255)
        self._blank_tolerance.setValue(245)
        self._blank_tolerance.setToolTip(
            self.tr(
                "Valor de gris (0-255) por encima del cual un píxel\n"
                "se considera blanco. 245 = casi blanco puro.\n"
                "Reducir si los escáneres producen fondos grisáceos."
            )
        )
        self._blank_tolerance_label = self.tr("Tolerancia de blanco:")
        blank_form.addRow(self._blank_tolerance_label, self._blank_tolerance)

        layout.addWidget(blank_group)

        # Cargar configuraciones desde ai_config_json
        self._load_barcode_config(app)
        self._load_blank_config(app)

        self._on_blank_enabled_changed(self._blank_enabled.isChecked())

        layout.addStretch()

    # ------------------------------------------------------------------
    # Pestañas del Workbench (paridad FlexibarNET10)
    # ------------------------------------------------------------------

    def _entry_titles(self) -> dict[str, str]:
        return {
            BARCODES: self.tr("Barcodes de la página (panel fijo)"),
            CAMPOS: self.tr("Campos de lote (panel fijo)"),
            VERIFICACION: self.tr("Verificación"),
            OCR: self.tr("OCR"),
            LOG: self.tr("Log"),
        }

    def _build_workbench_layout_group(self, app: Application) -> QGroupBox:
        group = QGroupBox(self.tr("Pestañas del Workbench"))
        box = QVBoxLayout(group)
        box.setContentsMargins(12, 16, 12, 12)
        hint = QLabel(
            self.tr(
                "Las dos primeras entradas son paneles fijos, siempre encima de las "
                "pestañas: desmárcalas para ocultarlos. El panel de campos solo "
                "aparece si la aplicación tiene campos de lote. Reordena las "
                "pestañas y desactiva las que no necesite el operador."
            )
        )
        hint.setWordWrap(True)
        hint.setProperty("cssClass", "info")
        box.addWidget(hint)

        row = QHBoxLayout()
        self._layout_list = QListWidget()
        self._layout_list.setObjectName("workbenchLayoutList")
        titles = self._entry_titles()
        for entry in WorkbenchLayout.from_json(
            getattr(app, "workbench_layout_json", "") or ""
        ).entries:
            item = QListWidgetItem(titles[entry.id])
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked if entry.visible else Qt.CheckState.Unchecked
            )
            self._layout_list.addItem(item)
        # Alto para ver las cinco entradas sin scroll interno.
        rows = self._layout_list.count()
        row_h = max(self._layout_list.sizeHintForRow(0), 24)
        self._layout_list.setFixedHeight(
            row_h * rows + 2 * self._layout_list.frameWidth() + 8
        )
        row.addWidget(self._layout_list, 1)

        buttons = QVBoxLayout()
        self._btn_layout_up = QPushButton("▲")
        self._btn_layout_up.setToolTip(self.tr("Subir la pestaña seleccionada"))
        self._btn_layout_down = QPushButton("▼")
        self._btn_layout_down.setToolTip(self.tr("Bajar la pestaña seleccionada"))
        for btn in (self._btn_layout_up, self._btn_layout_down):
            btn.setFixedWidth(36)
            buttons.addWidget(btn)
        buttons.addStretch(1)
        row.addLayout(buttons)
        box.addLayout(row)

        self._btn_layout_up.clicked.connect(lambda: self._move_layout_entry(-1))
        self._btn_layout_down.clicked.connect(lambda: self._move_layout_entry(1))
        self._layout_list.currentRowChanged.connect(self._refresh_layout_buttons)
        self._refresh_layout_buttons(self._layout_list.currentRow())
        return group

    def _refresh_layout_buttons(self, row: int) -> None:
        """Los paneles fijos no se reordenan; las pestañas, entre sí."""
        first_tab = len(PANEL_IDS)
        last = self._layout_list.count() - 1
        is_tab = row >= first_tab
        self._btn_layout_up.setEnabled(is_tab and row > first_tab)
        self._btn_layout_down.setEnabled(is_tab and row < last)

    def _move_layout_entry(self, delta: int) -> None:
        row = self._layout_list.currentRow()
        target = row + delta
        if row < len(PANEL_IDS) or not (
            len(PANEL_IDS) <= target < self._layout_list.count()
        ):
            return
        item = self._layout_list.takeItem(row)
        self._layout_list.insertItem(target, item)
        self._layout_list.setCurrentRow(target)

    def current_workbench_layout(self) -> WorkbenchLayout:
        """Layout tal como está en la lista (orden y casillas)."""
        entries = []
        for i in range(self._layout_list.count()):
            item = self._layout_list.item(i)
            entries.append(
                LayoutEntry(
                    item.data(Qt.ItemDataRole.UserRole),
                    item.checkState() == Qt.CheckState.Checked,
                )
            )
        return WorkbenchLayout(tuple(entries))

    @staticmethod
    def _parse_ai_config(app: Application) -> dict:
        """Parsea ai_config_json con fallback a dict vacío."""
        try:
            return json.loads(app.ai_config_json or "{}")
        except json.JSONDecodeError, TypeError:
            return {}

    def _load_barcode_config(self, app: Application) -> None:
        """Carga configuración de barcode manual desde ai_config_json."""
        config = self._parse_ai_config(app)
        self._bc_regex_edit.setText(config.get("barcode_regex", ""))
        self._bc_fixed_edit.setText(config.get("barcode_fixed_value", ""))

    def _load_blank_config(self, app: Application) -> None:
        """Carga configuracion de deteccion de blancos desde ai_config_json."""
        config = self._parse_ai_config(app)
        self._blank_enabled.setChecked(config.get("blank_detection", False))
        self._blank_threshold.setValue(config.get("blank_content_threshold", 1.0))
        self._blank_tolerance.setValue(config.get("blank_white_tolerance", 245))

    def _on_blank_enabled_changed(self, enabled: bool) -> None:
        """Habilita/deshabilita controles de deteccion de blancos."""
        self._blank_threshold.setEnabled(enabled)
        self._blank_tolerance.setEnabled(enabled)

    def apply_to(self, app: Application) -> None:
        """Aplica los valores del formulario al objeto Application."""
        app.name = self._name_edit.text().strip()
        app.description = self._desc_edit.toPlainText().strip()
        app.active = self._active_check.isChecked()
        app.scanner_backend = self._scanner_combo.currentText()
        app.auto_transfer = self._auto_transfer.isChecked()
        app.close_after_transfer = self._close_after.isChecked()
        app.hide_add_barcode_button = self._hide_add_barcode.isChecked()
        app.workbench_layout_json = self.current_workbench_layout().to_json()

        config = self._parse_ai_config(app)
        config["barcode_regex"] = self._bc_regex_edit.text().strip()
        config["barcode_fixed_value"] = self._bc_fixed_edit.text().strip()
        config["blank_detection"] = self._blank_enabled.isChecked()
        config["blank_content_threshold"] = self._blank_threshold.value()
        config["blank_white_tolerance"] = self._blank_tolerance.value()
        app.ai_config_json = json.dumps(config, ensure_ascii=False)
