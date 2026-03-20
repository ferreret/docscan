"""Diálogo principal del configurador de aplicación.

Organiza la configuración en pestañas: General, Pipeline, Eventos,
Transferencia, etc.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.application import Application
from app.ui.configurator.tabs.tab_general import GeneralTab
from app.ui.configurator.tabs.tab_image import ImageTab
from app.ui.configurator.tabs.tab_batch_fields import BatchFieldsTab
from app.ui.configurator.tabs.tab_pipeline import PipelineTab
from app.ui.configurator.tabs.tab_events import EventsTab
from app.ui.configurator.tabs.tab_transfer import TransferTab

log = logging.getLogger(__name__)


class AppConfigurator(QDialog):
    """Diálogo de configuración de una aplicación.

    Args:
        application: Objeto Application a configurar.
        session_factory: Fábrica de sesiones SQLAlchemy.
    """

    def __init__(
        self,
        application: Application,
        session_factory: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app = application
        self._session_factory = session_factory
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(f"Configurar — {self._app.name}")
        self.setMinimumSize(800, 600)
        self.resize(950, 700)

        layout = QVBoxLayout(self)

        # Pestañas
        self._tabs = QTabWidget()

        self._tab_general = GeneralTab(self._app)
        self._tab_image = ImageTab(self._app)
        self._tab_batch_fields = BatchFieldsTab(self._app)
        self._tab_pipeline = PipelineTab(self._app)
        self._tab_events = EventsTab(self._app)
        self._tab_transfer = TransferTab(self._app)

        self._tabs.addTab(self._tab_general, "General")
        self._tabs.addTab(self._tab_image, "Imagen")
        self._tabs.addTab(self._tab_batch_fields, "Campos de Lote")
        self._tabs.addTab(self._tab_pipeline, "Pipeline")
        self._tabs.addTab(self._tab_events, "Eventos")
        self._tabs.addTab(self._tab_transfer, "Transferencia")

        layout.addWidget(self._tabs)

        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        """Guarda los cambios en la BD."""
        try:
            # Recoger datos de cada pestaña
            self._tab_general.apply_to(self._app)
            self._tab_image.apply_to(self._app)
            self._tab_batch_fields.apply_to(self._app)
            self._tab_pipeline.apply_to(self._app)
            self._tab_events.apply_to(self._app)
            self._tab_transfer.apply_to(self._app)

            # Persistir
            with self._session_factory() as session:
                merged = session.merge(self._app)
                session.commit()
                # Actualizar referencia local
                session.refresh(merged)
                self._app = merged

            log.info("Aplicación '%s' guardada", self._app.name)
            self.accept()

        except Exception as e:
            log.error("Error guardando configuración: %s", e)
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo guardar la configuración:\n{e}",
            )
