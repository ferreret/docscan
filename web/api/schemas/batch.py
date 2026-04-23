"""Schemas Pydantic para lotes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.batch import BATCH_STATES


class BatchCreate(BaseModel):
    """Datos para crear un lote."""

    application_id: int
    folder_path: str = ""
    fields_json: str = "{}"


class BatchUpdate(BaseModel):
    """Datos para actualizar un lote (todos opcionales)."""

    state: str | None = None
    folder_path: str | None = None
    fields_json: str | None = None
    stats_json: str | None = None
    page_count: int | None = None

    @field_validator("state")
    @classmethod
    def _validar_estado(cls, v: str | None) -> str | None:
        if v is not None and v not in BATCH_STATES:
            raise ValueError(
                f"Estado inválido. Valores permitidos: {', '.join(BATCH_STATES)}"
            )
        return v


class BatchResponse(BaseModel):
    """Respuesta con datos completos de un lote."""

    id: int
    tenant_id: int | None
    application_id: int
    state: str
    folder_path: str
    hostname: str
    username: str
    page_count: int
    fields_json: str
    stats_json: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchListItem(BaseModel):
    """Resumen de lote para listados."""

    id: int
    application_id: int
    state: str
    page_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReorderBatchIn(BaseModel):
    """Nuevo orden de páginas del lote (lista de page_ids en orden deseado)."""

    page_ids: list[int]
