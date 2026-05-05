"""Schemas para el dispatcher de eventos lifecycle del workbench web."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventFireIn(BaseModel):
    """Payload para disparar un evento lifecycle."""

    page_id: int | None = None
    key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class EventResult(BaseModel):
    """Respuesta tipada tras ejecutar un script de evento."""

    executed: bool
    result: Any = None
    cancel: bool = False
    target_page_id: int | None = None
    fields_updated: dict[str, Any] = Field(default_factory=dict)
    batch_fields_updated: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, str]] = Field(default_factory=list)
    error: str | None = None
