"""Repositorio de lotes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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

    def get_all(self) -> list[Batch]:
        """Devuelve todos los lotes ordenados por fecha descendente."""
        stmt = select(Batch).order_by(Batch.created_at.desc())
        return list(self._session.scalars(stmt))

    def get_filtered(
        self,
        state: str | None = None,
        application_id: int | None = None,
        hostname: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Batch]:
        """Devuelve lotes filtrados por criterios opcionales."""
        stmt = select(Batch)

        if state:
            stmt = stmt.where(Batch.state == state)
        if application_id is not None:
            stmt = stmt.where(Batch.application_id == application_id)
        if hostname:
            stmt = stmt.where(Batch.hostname == hostname)
        if date_from:
            stmt = stmt.where(Batch.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Batch.created_at <= date_to)

        stmt = stmt.order_by(Batch.created_at.desc())
        return list(self._session.scalars(stmt))

    def get_distinct_hostnames(self) -> list[str]:
        """Devuelve los hostnames únicos de los lotes."""
        stmt = (
            select(Batch.hostname)
            .where(Batch.hostname != "")
            .distinct()
            .order_by(Batch.hostname)
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
