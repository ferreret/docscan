"""Repositorio de historial de operaciones."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operation_history import OperationHistory


class OperationHistoryRepository:
    """Operaciones sobre el historial inmutable de operaciones."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: OperationHistory) -> OperationHistory:
        """Añade una entrada al historial."""
        self._session.add(entry)
        self._session.flush()
        return entry

    def get_by_batch(self, batch_id: int) -> list[OperationHistory]:
        """Devuelve todo el historial de un lote, ordenado cronológicamente."""
        stmt = (
            select(OperationHistory)
            .where(OperationHistory.batch_id == batch_id)
            .order_by(OperationHistory.timestamp.desc())
        )
        return list(self._session.scalars(stmt))
