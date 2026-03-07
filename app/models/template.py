"""Modelo ORM de Plantilla de extracción IA."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Template(Base):
    """Plantilla de extracción de campos por IA.

    Define el prompt, los campos esperados y el proveedor objetivo.
    """

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(20), default="anthropic")

    # Prompt con variables interpolables ({page.barcodes[0].value}, etc.)
    prompt: Mapped[str] = mapped_column(Text, default="")

    # Campos esperados como JSON: [{"name": "...", "type": "...", ...}]
    fields_json: Mapped[str] = mapped_column(Text, default="[]")

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relación
    application: Mapped["Application"] = relationship(  # noqa: F821
        back_populates="templates",
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name='{self.name}')>"
