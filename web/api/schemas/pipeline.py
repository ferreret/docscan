"""Schemas pydantic para el editor de pipeline.

La validación fina de cada step se delega a
``app.pipeline.serializer.deserialize()`` (misma fuente que usa el runner).
Por eso ``StepPayload`` permite campos extra y solo valida ``id``,
``type`` y ``enabled``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StepPayload(BaseModel):
    """Representa un step en el JSON request/response.

    Los campos específicos del tipo (engine, symbologies, etc.) se
    aceptan como ``extra`` y se validan en backend vía ``deserialize()``.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    type: Literal["image_op", "barcode", "ocr", "script"]
    enabled: bool = True


class PipelineUpdate(BaseModel):
    """Body del ``PUT /applications/{id}/pipeline``."""

    steps: list[StepPayload]


class PipelineResponse(BaseModel):
    """Response del ``GET`` y el ``PUT``."""

    steps: list[dict[str, Any]]
