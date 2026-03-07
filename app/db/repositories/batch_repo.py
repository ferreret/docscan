"""Repositorio de lotes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.batch import Batch


class BatchRepository:
    """Operaciones CRUD sobre lotes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, batch_id: int) -> Batch | None:
        return self._session.get(Batch, batch_id)

    def get_by_application(self, app_id: int) -> list[Batch]:
        stmt = (
            select(Batch)
            .where(Batch.application_id == app_id)
            .order_by(Batch.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_by_state(self, state: str) -> list[Batch]:
        stmt = (
            select(Batch)
            .where(Batch.state == state)
            .order_by(Batch.created_at)
        )
        return list(self._session.scalars(stmt))

    def save(self, batch: Batch) -> Batch:
        self._session.add(batch)
        self._session.flush()
        return batch

    def delete(self, batch_id: int) -> None:
        batch = self.get_by_id(batch_id)
        if batch:
            self._session.delete(batch)
            self._session.flush()
