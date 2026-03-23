"""Serialización y deserialización del pipeline: JSON <-> list[PipelineStep].

El pipeline se almacena en BD como JSON (columna ``pipeline_json``).
Este módulo convierte entre la representación JSON y la lista de
dataclasses tipadas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from app.pipeline.steps import REMOVED_STEP_TYPES, STEP_TYPE_MAP, PipelineStep

log = logging.getLogger(__name__)


class PipelineSerializationError(Exception):
    """Error al serializar o deserializar el pipeline."""


def serialize(steps: list[PipelineStep]) -> str:
    """Convierte una lista de pasos a JSON string.

    Args:
        steps: Lista de PipelineStep (o subclases).

    Returns:
        JSON string con la representación del pipeline.
    """
    raw = [_step_to_dict(step) for step in steps]
    return json.dumps(raw, ensure_ascii=False)


def deserialize(json_str: str) -> list[PipelineStep]:
    """Convierte un JSON string a lista de pasos tipados.

    Args:
        json_str: JSON string del pipeline.

    Returns:
        Lista de PipelineStep con la subclase correcta por tipo.

    Raises:
        PipelineSerializationError: Si el JSON es inválido o contiene
            tipos de paso desconocidos.
    """
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise PipelineSerializationError(f"JSON inválido: {e}") from e

    if not isinstance(raw, list):
        raise PipelineSerializationError(
            "El pipeline debe ser una lista de pasos"
        )

    steps: list[PipelineStep] = []
    for i, data in enumerate(raw):
        if not isinstance(data, dict):
            raise PipelineSerializationError(
                f"Paso {i}: se esperaba un objeto, se obtuvo {type(data).__name__}"
            )
        step = _dict_to_step(data, index=i)
        if step is not None:
            steps.append(step)

    return steps


def _step_to_dict(step: PipelineStep) -> dict[str, Any]:
    """Convierte un PipelineStep a diccionario serializable.

    Convierte tuplas (como ``window``) a listas para compatibilidad JSON.
    """
    data = asdict(step)
    # Las tuplas se convierten a listas por asdict(); eso es correcto para JSON
    return data


def _dict_to_step(data: dict[str, Any], index: int) -> PipelineStep | None:
    """Convierte un diccionario a la subclase correcta de PipelineStep.

    Args:
        data: Diccionario con los campos del paso.
        index: Posición en la lista (para mensajes de error).

    Returns:
        La subclase correcta de PipelineStep, o None si el tipo está
        en REMOVED_STEP_TYPES (compatibilidad con pipelines antiguos).
    """
    step_type = data.get("type")
    if not step_type:
        raise PipelineSerializationError(
            f"Paso {index}: falta el campo 'type'"
        )

    # Tolerancia: tipos eliminados se saltan (compatibilidad con pipelines antiguos)
    if step_type in REMOVED_STEP_TYPES:
        log.debug("Paso %d: tipo '%s' eliminado, saltando", index, step_type)
        return None

    cls = STEP_TYPE_MAP.get(step_type)
    if cls is None:
        raise PipelineSerializationError(
            f"Paso {index}: tipo desconocido '{step_type}'"
        )

    # Filtrar campos que no pertenecen al dataclass para tolerancia
    # ante campos extra (ej: versiones futuras del esquema)
    valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in valid_fields}

    # Convertir listas a tuplas donde el dataclass espera tuple
    _coerce_tuples(filtered, cls)

    try:
        return cls(**filtered)
    except TypeError as e:
        raise PipelineSerializationError(
            f"Paso {index} ('{step_type}'): {e}"
        ) from e


def _coerce_tuples(data: dict[str, Any], cls: type) -> None:
    """Convierte listas JSON a tuplas donde el dataclass lo requiere.

    Los campos ``window`` se almacenan como lista en JSON pero el
    dataclass los define como ``tuple[int,int,int,int] | None``.
    """
    for field_name in ("window",):
        value = data.get(field_name)
        if isinstance(value, list):
            data[field_name] = tuple(value)
