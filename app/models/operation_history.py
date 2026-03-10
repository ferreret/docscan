"""Modelo ORM de Historial de Operaciones (BAT-06).

Registro inmutable de cada cambio de estado, error y transferencia
de un lote, con timestamp y usuario.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class OperationHistory(Base):
    """Entrada inmutable del historial de operaciones de un lote."""

    __tablename__ = "operation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE")
    )
    operation: Mapped[str] = mapped_column(String(50))
    old_state: Mapped[str] = mapped_column(String(20), default="")
    new_state: Mapped[str] = mapped_column(String(20), default="")
    username: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relación
    batch: Mapped["Batch"] = relationship(  # noqa: F821
        back_populates="history",
    )

    def __repr__(self) -> str:
        return (
            f"<OperationHistory(id={self.id}, batch={self.batch_id}, "
            f"op='{self.operation}')>"
        )
