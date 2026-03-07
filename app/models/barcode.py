"""Modelo ORM de Barcode."""

from __future__ import annotations

from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Barcode(Base):
    """Código de barras detectado en una página.

    El campo ``role`` es asignado por scripts (ej: 'separator', 'content').
    El motor de barcode no asigna roles — es agnóstico.
    """

    __tablename__ = "barcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE")
    )

    value: Mapped[str] = mapped_column(Text)
    symbology: Mapped[str] = mapped_column(String(50))
    engine: Mapped[str] = mapped_column(String(10))  # "motor1" o "motor2"
    step_id: Mapped[str] = mapped_column(String(50))  # Paso que lo detectó
    quality: Mapped[float] = mapped_column(Float, default=0.0)

    # Posición en la imagen (x, y, w, h)
    pos_x: Mapped[int] = mapped_column(Integer, default=0)
    pos_y: Mapped[int] = mapped_column(Integer, default=0)
    pos_w: Mapped[int] = mapped_column(Integer, default=0)
    pos_h: Mapped[int] = mapped_column(Integer, default=0)

    # Rol asignado por script (vacío = sin rol)
    role: Mapped[str] = mapped_column(String(50), default="")

    # Relación
    page: Mapped["Page"] = relationship(  # noqa: F821
        back_populates="barcodes",
    )

    def __repr__(self) -> str:
        return f"<Barcode(id={self.id}, value='{self.value[:20]}', symbology='{self.symbology}')>"
