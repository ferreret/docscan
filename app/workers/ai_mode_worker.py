"""Worker QThread para el asistente AI MODE."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.services.ai_mode_assistant import (
    AiModeAssistantService,
    AiModeResponse,
)

log = logging.getLogger(__name__)


class AiModeWorker(QThread):
    """Hilo para ejecutar peticiones al asistente AI MODE.

    Signals:
        response_ready: Emitida con AiModeResponse al completar.
        error_occurred: Emitida con mensaje de error si falla.
    """

    response_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._service: AiModeAssistantService | None = None
        self._messages: list[dict[str, str]] = []
        self._apps_summary: str = "[]"

    def configure(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        self._service = AiModeAssistantService(provider, api_key, model)

    def send_message(
        self,
        messages: list[dict[str, str]],
        apps_summary: str,
    ) -> None:
        if self.isRunning():
            log.warning("AiModeWorker: peticion ignorada, hilo ocupado.")
            self.error_occurred.emit("El asistente aun esta procesando. Espera la respuesta.")
            return
        self._messages = messages
        self._apps_summary = apps_summary
        self.start()

    def run(self) -> None:
        if self._service is None:
            self.error_occurred.emit("Servicio no configurado.")
            return
        try:
            result = self._service.generate(self._messages, self._apps_summary)
            self.response_ready.emit(result)
        except Exception as e:
            log.error("Error en AiModeWorker: %s", e)
            self.error_occurred.emit(str(e))
