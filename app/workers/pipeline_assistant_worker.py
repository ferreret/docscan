"""Worker QThread para el asistente IA de pipelines.

Ejecuta PipelineAssistantService en un hilo secundario para no
bloquear la UI durante las llamadas API.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.services.pipeline_assistant import (
    AssistantResponse,
    PipelineAssistantService,
)

log = logging.getLogger(__name__)


class PipelineAssistantWorker(QThread):
    """Hilo para ejecutar peticiones al asistente IA.

    Signals:
        response_ready: Emitida con AssistantResponse al completar.
        error_occurred: Emitida con mensaje de error si falla.
    """

    response_ready = Signal(object)  # AssistantResponse
    error_occurred = Signal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._service: PipelineAssistantService | None = None
        self._mode: str = "pipeline"
        # Datos para pipeline
        self._messages: list[dict[str, str]] = []
        self._current_pipeline_json: str = "[]"
        # Datos para eventos
        self._event_name: str = ""
        self._current_code: str = ""

    def configure(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        """Configura el servicio con proveedor y credenciales."""
        self._service = PipelineAssistantService(provider, api_key, model)

    def send_pipeline_message(
        self,
        messages: list[dict[str, str]],
        pipeline_json: str,
    ) -> None:
        """Envia un mensaje en modo pipeline y lanza el hilo."""
        self._mode = "pipeline"
        self._messages = messages
        self._current_pipeline_json = pipeline_json
        if not self.isRunning():
            self.start()

    def send_event_message(
        self,
        messages: list[dict[str, str]],
        event_name: str,
        current_code: str,
    ) -> None:
        """Envia un mensaje en modo evento y lanza el hilo."""
        self._mode = "event"
        self._messages = messages
        self._event_name = event_name
        self._current_code = current_code
        if not self.isRunning():
            self.start()

    def run(self) -> None:
        """Ejecuta la peticion al servicio en hilo secundario."""
        if self._service is None:
            self.error_occurred.emit("Servicio no configurado.")
            return

        try:
            if self._mode == "pipeline":
                result = self._service.generate_pipeline(
                    messages=self._messages,
                    current_pipeline_json=self._current_pipeline_json,
                )
            else:
                result = self._service.generate_event_code(
                    messages=self._messages,
                    event_name=self._event_name,
                    current_code=self._current_code,
                )
            self.response_ready.emit(result)
        except Exception as e:
            log.error("Error en PipelineAssistantWorker: %s", e)
            self.error_occurred.emit(str(e))
