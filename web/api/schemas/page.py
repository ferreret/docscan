"""Schemas Pydantic para páginas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BarcodeResponse(BaseModel):
    """Barcode detectado en una página."""

    id: int
    value: str
    symbology: str
    engine: str
    step_id: str
    quality: float
    pos_x: int
    pos_y: int
    pos_w: int
    pos_h: int
    role: str

    model_config = {"from_attributes": True}


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
    barcodes: list[BarcodeResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageListItem(BaseModel):
    """Resumen de página para listados."""

    id: int
    batch_id: int
    page_index: int
    needs_review: bool
    review_reason: str
    is_blank: bool
    is_excluded: bool
    pipeline_processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PageUploadResponse(BaseModel):
    """Respuesta tras un upload: páginas creadas y nuevo total del lote."""

    created: list[PageResponse]
    batch_page_count: int


class PagePatchIn(BaseModel):
    """Patch parcial de flags de página."""

    is_excluded: bool | None = None
    needs_review: bool | None = None
    review_reason: str | None = None


class RotatePageIn(BaseModel):
    """Número de rotaciones 90° CW a aplicar."""

    turns: int = Field(default=1, ge=1, le=3)


class AddBarcodeIn(BaseModel):
    """Payload para añadir un barcode manual."""

    value: str = Field(min_length=1)
    symbology: str = Field(default="MANUAL", min_length=1, max_length=50)

    @field_validator("value")
    @classmethod
    def _value_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("value no puede ser solo espacios")
        return v.strip()
