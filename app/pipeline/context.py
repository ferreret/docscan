"""PipelineContext — control de flujo del pipeline desde scripts.

El objeto ``pipeline`` que reciben los ScriptStep expone métodos
para alterar el orden de ejecución de forma declarativa.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.pipeline.steps import PipelineStep

log = logging.getLogger(__name__)

MAX_STEP_REPEATS: int = 3
"""Límite por defecto de repeticiones por paso. Configurable en settings."""


class PipelineAbortError(Exception):
    """El pipeline fue abortado explícitamente o por exceder repeat_step."""


class PipelineContext:
    """Controla la ejecución del pipeline para una página concreta.

    Args:
        steps: Lista ordenada de pasos del pipeline.
        max_repeats: Máximo de repeticiones permitidas por paso.
    """

    def __init__(
        self,
        steps: list[PipelineStep],
        max_repeats: int = MAX_STEP_REPEATS,
    ) -> None:
        self._steps = list(steps)
        self._max_repeats = max_repeats
        self._cursor: int = 0
        self._skipped: set[str] = set()
        self._repeat_queue: list[PipelineStep] = []
        self._repeat_counts: dict[str, int] = {}
        self._results: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}
        self._current_image: np.ndarray | None = None
        self._aborted: bool = False
        self._abort_reason: str = ""

    # ------------------------------------------------------------------
    # Iteración
    # ------------------------------------------------------------------

    def has_next(self) -> bool:
        """¿Quedan pasos por ejecutar?"""
        if self._aborted:
            return False
        if self._repeat_queue:
            return True
        return self._cursor < len(self._steps)

    def next_step(self) -> PipelineStep:
        """Devuelve el siguiente paso a ejecutar.

        Prioriza los pasos encolados por ``repeat_step`` sobre la
        secuencia normal.
        """
        if self._repeat_queue:
            return self._repeat_queue.pop(0)
        step = self._steps[self._cursor]
        self._cursor += 1
        return step

    def is_skipped(self, step_id: str) -> bool:
        """Comprueba si un paso ha sido marcado para saltar."""
        return step_id in self._skipped

    # ------------------------------------------------------------------
    # Control de flujo (API pública para scripts)
    # ------------------------------------------------------------------

    def skip_step(self, step_id: str) -> None:
        """Salta un paso específico por su id."""
        self._skipped.add(step_id)

    def skip_to(self, step_id: str) -> None:
        """Salta todos los pasos hasta llegar a ``step_id``.

        Los pasos intermedios se marcan como saltados.
        El paso ``step_id`` sí se ejecutará.
        """
        for i in range(self._cursor, len(self._steps)):
            if self._steps[i].id == step_id:
                # Marcar intermedios como saltados
                for j in range(self._cursor, i):
                    self._skipped.add(self._steps[j].id)
                self._cursor = i
                return
        log.warning("skip_to: paso '%s' no encontrado", step_id)

    def abort(self, reason: str = "") -> None:
        """Detiene el pipeline para esta página."""
        self._aborted = True
        self._abort_reason = reason
        raise PipelineAbortError(reason)

    def repeat_step(self, step_id: str) -> None:
        """Re-ejecuta un paso ya ejecutado.

        Raises:
            PipelineAbortError: Si el paso supera el límite de repeticiones.
        """
        count = self._repeat_counts.get(step_id, 0)
        if count >= self._max_repeats:
            self._aborted = True
            raise PipelineAbortError(
                f"Paso '{step_id}' superó el límite de "
                f"{self._max_repeats} repeticiones"
            )
        self._repeat_counts[step_id] = count + 1

        for step in self._steps:
            if step.id == step_id:
                self._repeat_queue.append(step)
                return
        log.warning("repeat_step: paso '%s' no encontrado", step_id)

    # ------------------------------------------------------------------
    # Imagen en curso
    # ------------------------------------------------------------------

    def replace_image(self, image: np.ndarray) -> None:
        """Reemplaza la imagen en curso del pipeline."""
        self._current_image = image

    @property
    def current_image(self) -> np.ndarray | None:
        """Imagen actual (None si no se ha reemplazado)."""
        return self._current_image

    # ------------------------------------------------------------------
    # Resultados y metadatos
    # ------------------------------------------------------------------

    def set_step_result(self, step_id: str, result: Any) -> None:
        """Almacena el resultado de un paso (uso interno del executor)."""
        self._results[step_id] = result

    def get_step_result(self, step_id: str) -> Any:
        """Obtiene el resultado de un paso ya ejecutado."""
        return self._results.get(step_id)

    def set_metadata(self, key: str, value: Any) -> None:
        """Almacena metadatos accesibles en pasos posteriores."""
        self._metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        """Recupera metadatos establecidos previamente."""
        return self._metadata.get(key)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def abort_reason(self) -> str:
        return self._abort_reason
