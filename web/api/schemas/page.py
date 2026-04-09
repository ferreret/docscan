"""Schemas Pydantic para páginas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PageResponse(BaseModel):
    """Respuesta con datos completos de una página."""

    id: int
    batch_id: int
    page_index: int
    image_path: str
    ocr_text: str
    index_fields_json: str
    needs_review: bool
    review_reason: str
    is_blank: bool
    is_excluded: bool
    pipeline_processed: bool
    processing_errors_json: str
    script_errors_json: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageListItem(BaseModel):
    """Resumen de página para listados."""

    id: int
    batch_id: int
    page_index: int
    needs_review: bool
    is_blank: bool
    pipeline_processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PageUploadResponse(BaseModel):
    """Respuesta tras un upload: páginas creadas y nuevo total del lote."""

    created: list[PageResponse]
    batch_page_count: int
