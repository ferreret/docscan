"""Repositorio de aplicaciones."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application


class ApplicationRepository:
    """Operaciones CRUD sobre aplicaciones.

    Recibe la Session por parámetro; no la crea internamente.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[Application]:
        """Todas las aplicaciones (activas primero, luego por nombre)."""
        stmt = select(Application).order_by(
            Application.active.desc(), Application.name,
        )
        return list(self._session.scalars(stmt))

    def get_all_active(self) -> list[Application]:
        """Solo aplicaciones activas."""
        stmt = (
            select(Application)
            .where(Application.active.is_(True))
            .order_by(Application.name)
        )
        return list(self._session.scalars(stmt))

    def get_by_id(self, app_id: int) -> Application | None:
        return self._session.get(Application, app_id)

    def get_by_name(self, name: str) -> Application | None:
        stmt = select(Application).where(Application.name == name)
        return self._session.scalar(stmt)

    def save(self, app: Application) -> Application:
        """Inserta o actualiza una aplicación."""
        self._session.add(app)
        self._session.flush()
        return app

    def delete(self, app_id: int) -> None:
        app = self.get_by_id(app_id)
        if app:
            self._session.delete(app)
            self._session.flush()
