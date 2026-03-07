"""Modelo ORM de Aplicación (perfil de proceso)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Application(Base):
    """Aplicación configurable (perfil de proceso).

    Cada aplicación define un pipeline, scripts, transferencia,
    campos de lote e indexación de forma independiente.
    """

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Pipeline como JSON (serializado con pipeline/serializer.py)
    pipeline_json: Mapped[str] = mapped_column(Text, default="[]")

    # Scripts de eventos (entry points de ciclo de vida)
    events_json: Mapped[str] = mapped_column(Text, default="{}")

    # Configuración de transferencia
    transfer_json: Mapped[str] = mapped_column(Text, default="{}")

    # Campos de lote e indexación
    batch_fields_json: Mapped[str] = mapped_column(Text, default="[]")
    index_fields_json: Mapped[str] = mapped_column(Text, default="[]")

    # Opciones generales
    auto_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    close_after_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    background_color: Mapped[str] = mapped_column(String(7), default="")
    output_format: Mapped[str] = mapped_column(String(20), default="tiff")
    default_tab: Mapped[str] = mapped_column(String(20), default="lote")
    scanner_backend: Mapped[str] = mapped_column(String(10), default="twain")

    # IA / OCR
    ai_config_json: Mapped[str] = mapped_column(Text, default="{}")

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    batches: Mapped[list["Batch"]] = relationship(  # noqa: F821
        back_populates="application",
        cascade="all, delete-orphan",
    )
    templates: Mapped[list["Template"]] = relationship(  # noqa: F821
        back_populates="application",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, name='{self.name}')>"
