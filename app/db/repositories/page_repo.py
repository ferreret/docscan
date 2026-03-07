"""Repositorio de páginas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.page import Page


class PageRepository:
    """Operaciones CRUD sobre páginas."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, page_id: int) -> Page | None:
        return self._session.get(Page, page_id)

    def get_by_batch(self, batch_id: int) -> list[Page]:
        stmt = (
            select(Page)
            .where(Page.batch_id == batch_id)
            .order_by(Page.page_index)
        )
        return list(self._session.scalars(stmt))

    def get_needs_review(self, batch_id: int) -> list[Page]:
        stmt = (
            select(Page)
            .where(Page.batch_id == batch_id, Page.needs_review.is_(True))
            .order_by(Page.page_index)
        )
        return list(self._session.scalars(stmt))

    def save(self, page: Page) -> Page:
        self._session.add(page)
        self._session.flush()
        return page

    def save_all(self, pages: list[Page]) -> list[Page]:
        self._session.add_all(pages)
        self._session.flush()
        return pages

    def delete(self, page_id: int) -> None:
        page = self.get_by_id(page_id)
        if page:
            self._session.delete(page)
            self._session.flush()

    def count_by_batch(self, batch_id: int) -> int:
        stmt = (
            select(Page.id)
            .where(Page.batch_id == batch_id)
        )
        return len(list(self._session.scalars(stmt)))
