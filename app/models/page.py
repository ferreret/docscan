"""Modelo ORM de Página."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Page(Base):
    """Página individual dentro de un lote."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE")
    )
    page_index: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(Text, default="")

    # Resultados del pipeline
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    index_fields_json: Mapped[str] = mapped_column(Text, default="{}")

    # Flags
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str] = mapped_column(Text, default="")
    is_blank: Mapped[bool] = mapped_column(Boolean, default=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    # Pipeline
    pipeline_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Errores de procesado
    processing_errors_json: Mapped[str] = mapped_column(Text, default="[]")
    script_errors_json: Mapped[str] = mapped_column(Text, default="[]")

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    batch: Mapped["Batch"] = relationship(  # noqa: F821
        back_populates="pages",
    )
    barcodes: Mapped[list["Barcode"]] = relationship(  # noqa: F821
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="Barcode.id",
    )

    def __repr__(self) -> str:
        return f"<Page(id={self.id}, index={self.page_index})>"
