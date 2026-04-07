"""Schemas Pydantic para aplicaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    """Datos para crear una aplicación."""

    name: str
    description: str = ""
    active: bool = True
    pipeline_json: str = "[]"
    events_json: str = "{}"
    transfer_json: str = "{}"
    batch_fields_json: str = "[]"
    index_fields_json: str = "[]"
    auto_transfer: bool = False
    close_after_transfer: bool = False
    background_color: str = ""
    output_format: str = "tiff"
    default_tab: str = "lote"
    scanner_backend: str = ""
    image_config_json: str = "{}"
    ai_config_json: str = "{}"


class ApplicationUpdate(BaseModel):
    """Datos para actualizar una aplicación (todos opcionales)."""

    name: str | None = None
    description: str | None = None
    active: bool | None = None
    pipeline_json: str | None = None
    events_json: str | None = None
    transfer_json: str | None = None
    batch_fields_json: str | None = None
    index_fields_json: str | None = None
    auto_transfer: bool | None = None
    close_after_transfer: bool | None = None
    background_color: str | None = None
    output_format: str | None = None
    default_tab: str | None = None
    scanner_backend: str | None = None
    image_config_json: str | None = None
    ai_config_json: str | None = None


class ApplicationResponse(BaseModel):
    """Respuesta con datos de una aplicación."""

    id: int
    tenant_id: int | None
    name: str
    description: str
    active: bool
    pipeline_json: str
    events_json: str
    transfer_json: str
    batch_fields_json: str
    index_fields_json: str
    auto_transfer: bool
    close_after_transfer: bool
    background_color: str
    output_format: str
    default_tab: str
    scanner_backend: str
    image_config_json: str
    ai_config_json: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationListItem(BaseModel):
    """Resumen de aplicación para listados."""

    id: int
    name: str
    description: str
    active: bool
    output_format: str
    created_at: datetime

    model_config = {"from_attributes": True}
