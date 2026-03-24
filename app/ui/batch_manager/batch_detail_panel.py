"""Panel de detalle de un lote seleccionado (BAT-04, BAT-06, BAT-09)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.batch_manager.batch_list_widget import STATE_LABELS

log = logging.getLogger(__name__)


class BatchDetailPanel(QTabWidget):
    """Panel con pestañas de detalle de un lote.

    Pestañas: General, Estadísticas, Páginas, Historial.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_general_tab()
        self._build_stats_tab()
        self._build_pages_tab()
        self._build_history_tab()

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    def _build_general_tab(self) -> None:
        """Pestaña de información general del lote."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._lbl_id = QLabel("-")
        self._lbl_app = QLabel("-")
        self._lbl_state = QLabel("-")
        self._lbl_hostname = QLabel("-")
        self._lbl_username = QLabel("-")
        self._lbl_pages = QLabel("-")
        self._lbl_created = QLabel("-")
        self._lbl_updated = QLabel("-")
        self._lbl_folder = QLabel("-")
        self._lbl_folder.setWordWrap(True)

        layout.addRow(self.tr("ID:"), self._lbl_id)
        layout.addRow(self.tr("Aplicación:"), self._lbl_app)
        layout.addRow(self.tr("Estado:"), self._lbl_state)
        layout.addRow(self.tr("Estación:"), self._lbl_hostname)
        layout.addRow(self.tr("Usuario:"), self._lbl_username)
        layout.addRow(self.tr("Páginas:"), self._lbl_pages)
        layout.addRow(self.tr("Creado:"), self._lbl_created)
        layout.addRow(self.tr("Actualizado:"), self._lbl_updated)
        layout.addRow(self.tr("Carpeta:"), self._lbl_folder)

        self.addTab(widget, self.tr("General"))

    def set_general_info(self, info: dict[str, Any]) -> None:
        """Establece la información general del lote."""
        self._lbl_id.setText(str(info.get("id", "-")))
        self._lbl_app.setText(info.get("app_name", "-"))
        state = info.get("state", "")
        self._lbl_state.setText(STATE_LABELS().get(state, state))
        self._lbl_hostname.setText(info.get("hostname", "-"))
        self._lbl_username.setText(info.get("username", "-"))
        self._lbl_pages.setText(str(info.get("page_count", 0)))
        self._lbl_created.setText(self._fmt_dt(info.get("created_at")))
        self._lbl_updated.setText(self._fmt_dt(info.get("updated_at")))
        self._lbl_folder.setText(info.get("folder_path", "-"))

    # ------------------------------------------------------------------
    # Estadísticas (BAT-09)
    # ------------------------------------------------------------------

    def _build_stats_tab(self) -> None:
        """Pestaña de estadísticas del lote."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Grupo: Páginas
        pages_group = QGroupBox(self.tr("Páginas"))
        pages_layout = QFormLayout(pages_group)
        self._lbl_stat_total = QLabel("0")
        self._lbl_stat_review = QLabel("0")
        self._lbl_stat_excluded = QLabel("0")
        self._lbl_stat_blank = QLabel("0")
        self._lbl_stat_errors = QLabel("0")
        pages_layout.addRow(self.tr("Total:"), self._lbl_stat_total)
        pages_layout.addRow(self.tr("Requieren revisión:"), self._lbl_stat_review)
        pages_layout.addRow(self.tr("Excluidas:"), self._lbl_stat_excluded)
        pages_layout.addRow(self.tr("En blanco:"), self._lbl_stat_blank)
        pages_layout.addRow(self.tr("Con errores:"), self._lbl_stat_errors)
        layout.addWidget(pages_group)

        # Grupo: Pipeline (stats_json)
        pipeline_group = QGroupBox(self.tr("Pipeline"))
        pipeline_layout = QVBoxLayout(pipeline_group)
        self._txt_pipeline_stats = QTextEdit()
        self._txt_pipeline_stats.setReadOnly(True)
        self._txt_pipeline_stats.setMaximumHeight(150)
        pipeline_layout.addWidget(self._txt_pipeline_stats)
        layout.addWidget(pipeline_group)

        layout.addStretch()
        self.addTab(widget, self.tr("Estadísticas"))

    def set_stats(self, stats: dict[str, Any], pipeline_stats_json: str = "{}") -> None:
        """Establece las estadísticas del lote."""
        self._lbl_stat_total.setText(str(stats.get("total_pages", 0)))
        self._lbl_stat_review.setText(str(stats.get("needs_review", 0)))
        self._lbl_stat_excluded.setText(str(stats.get("excluded", 0)))
        self._lbl_stat_blank.setText(str(stats.get("blank", 0)))
        self._lbl_stat_errors.setText(str(stats.get("with_errors", 0)))

        # Pipeline stats
        try:
            p_stats = json.loads(pipeline_stats_json)
            if p_stats:
                lines = []
                for key, val in p_stats.items():
                    lines.append(f"{key}: {val}")
                self._txt_pipeline_stats.setPlainText("\n".join(lines))
            else:
                self._txt_pipeline_stats.setPlainText(self.tr("Sin estadísticas de pipeline"))
        except (json.JSONDecodeError, TypeError):
            self._txt_pipeline_stats.setPlainText(self.tr("Sin estadísticas de pipeline"))

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------

    def _build_pages_tab(self) -> None:
        """Pestaña de lista de páginas del lote."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self._pages_table = QTableWidget()
        cols = [
            self.tr("#"), self.tr("Revisión"), self.tr("Excluida"),
            self.tr("Blanco"), self.tr("OCR"), self.tr("Errores"),
        ]
        self._pages_table.setColumnCount(len(cols))
        self._pages_table.setHorizontalHeaderLabels(cols)
        self._pages_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._pages_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._pages_table.verticalHeader().setVisible(False)
        self._pages_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self._pages_table)
        self.addTab(widget, self.tr("Páginas"))

    def set_pages(self, pages: list[dict[str, Any]]) -> None:
        """Carga la lista de páginas en la tabla."""
        self._pages_table.setRowCount(0)

        for row_idx, page in enumerate(pages):
            self._pages_table.insertRow(row_idx)

            items = [
                str(page.get("page_index", row_idx)),
                self.tr("Sí") if page.get("needs_review") else "",
                self.tr("Sí") if page.get("is_excluded") else "",
                self.tr("Sí") if page.get("is_blank") else "",
                self.tr("Sí") if page.get("ocr_text") else "",
                str(page.get("error_count", 0)) if page.get("error_count") else "",
            ]

            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if page.get("needs_review") and col_idx == 1:
                    item.setBackground(Qt.GlobalColor.yellow)
                self._pages_table.setItem(row_idx, col_idx, item)

    # ------------------------------------------------------------------
    # Historial (BAT-06)
    # ------------------------------------------------------------------

    def _build_history_tab(self) -> None:
        """Pestaña de historial inmutable de operaciones."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self._history_table = QTableWidget()
        cols = [
            self.tr("Fecha"), self.tr("Operación"), self.tr("Estado ant."),
            self.tr("Estado nuevo"), self.tr("Usuario"), self.tr("Mensaje"),
        ]
        self._history_table.setColumnCount(len(cols))
        self._history_table.setHorizontalHeaderLabels(cols)
        self._history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self._history_table)
        self.addTab(widget, self.tr("Historial"))

    def set_history(self, entries: list[dict[str, Any]]) -> None:
        """Carga el historial de operaciones."""
        self._history_table.setRowCount(0)

        for row_idx, entry in enumerate(entries):
            self._history_table.insertRow(row_idx)

            items = [
                self._fmt_dt(entry.get("timestamp")),
                entry.get("operation", ""),
                STATE_LABELS().get(entry.get("old_state", ""), entry.get("old_state", "")),
                STATE_LABELS().get(entry.get("new_state", ""), entry.get("new_state", "")),
                entry.get("username", ""),
                entry.get("message", ""),
            ]

            for col_idx, text in enumerate(items):
                self._history_table.setItem(
                    row_idx, col_idx, QTableWidgetItem(text),
                )

    # ------------------------------------------------------------------
    # Limpieza
    # ------------------------------------------------------------------

    def clear_all(self) -> None:
        """Limpia toda la información del panel."""
        for lbl in (
            self._lbl_id, self._lbl_app, self._lbl_state,
            self._lbl_hostname, self._lbl_username, self._lbl_pages,
            self._lbl_created, self._lbl_updated, self._lbl_folder,
        ):
            lbl.setText("-")

        for lbl in (
            self._lbl_stat_total, self._lbl_stat_review,
            self._lbl_stat_excluded, self._lbl_stat_blank,
            self._lbl_stat_errors,
        ):
            lbl.setText("0")

        self._txt_pipeline_stats.clear()
        self._pages_table.setRowCount(0)
        self._history_table.setRowCount(0)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_dt(dt: datetime | str | None) -> str:
        if dt is None:
            return "-"
        if isinstance(dt, str):
            return dt
        return dt.strftime("%d/%m/%Y %H:%M:%S")
