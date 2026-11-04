"""Worker de la validación previa a la transferencia.

``on_transfer_validate`` puede consultar servicios externos (LIS, HIS…): en
el hilo de la UI dejaba el Workbench congelado mientras tanto. Este hilo
ejecuta la validación ya preparada por el Workbench y devuelve el motivo de
rechazo, o ``None`` si se puede transferir.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger(__name__)


class ValidationWorker(QThread):
    """Ejecuta una validación en segundo plano.

    Signals:
        validated: motivo de rechazo (str) o ``None`` si el lote es válido.
    """

    validated = Signal(object)  # str | None

    def __init__(
        self,
        validate: Callable[[], str | None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._validate = validate

    def run(self) -> None:
        """Valida y emite el resultado; un fallo inesperado rechaza."""
        try:
            reason = self._validate()
        except Exception as e:
            log.exception("Error inesperado en la validación previa")
            reason = f"Ha fallado la validación previa a la transferencia: {e}"
        self.validated.emit(reason)
