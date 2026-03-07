"""Modelo ORM de Lote (batch)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# Estados válidos de un lote
BATCH_STATES = (
    "created",
    "read",
    "verified",
    "ready_to_export",
    "exported",
    "error_read",
    "error_export",
)


class Batch(Base):
    """Lote de documentos procesados por una aplicación."""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(20), default="created")
    folder_path: Mapped[str] = mapped_column(Text, default="")
    hostname: Mapped[str] = mapped_column(String(100), default="")
    username: Mapped[str] = mapped_column(String(100), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    # Campos de lote (valores introducidos por el usuario)
    fields_json: Mapped[str] = mapped_column(Text, default="{}")

    # Estadísticas del pipeline
    stats_json: Mapped[str] = mapped_column(Text, default="{}")

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    application: Mapped["Application"] = relationship(  # noqa: F821
        back_populates="batches",
    )
    pages: Mapped[list["Page"]] = relationship(  # noqa: F821
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="Page.page_index",
    )

    def __repr__(self) -> str:
        return f"<Batch(id={self.id}, state='{self.state}')>"
