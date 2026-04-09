"""Router CRUD de aplicaciones (tenant-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.schemas.application import (
    ApplicationCreate,
    ApplicationListItem,
    ApplicationResponse,
    ApplicationUpdate,
)
from web.api.storage import StorageDep

router = APIRouter()


def _get_app_or_404(
    app_id: int, tenant_id: int, db: Session,
) -> Application:
    """Obtiene una aplicación del tenant actual o lanza 404."""
    app = db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicación no encontrada",
        )
    return app


@router.get("", response_model=list[ApplicationListItem])
def list_applications(user: CurrentUser, db: SessionDep):
    """Lista las aplicaciones del tenant del usuario."""
    apps = db.execute(
        select(Application)
        .where(Application.tenant_id == user.tenant_id)
        .order_by(Application.name)
    ).scalars().all()
    return apps


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(
    data: ApplicationCreate, user: CurrentUser, db: SessionDep,
):
    """Crea una nueva aplicación en el tenant del usuario."""
    existing = db.execute(
        select(Application).where(
            Application.name == data.name,
            Application.tenant_id == user.tenant_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una aplicación con ese nombre",
        )

    app = Application(
        **data.model_dump(),
        tenant_id=user.tenant_id,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int, user: CurrentUser, db: SessionDep):
    """Obtiene una aplicación por ID."""
    return _get_app_or_404(app_id, user.tenant_id, db)


@router.patch("/{app_id}", response_model=ApplicationResponse)
def update_application(
    app_id: int, data: ApplicationUpdate, user: CurrentUser, db: SessionDep,
):
    """Actualiza una aplicación existente."""
    app = _get_app_or_404(app_id, user.tenant_id, db)

    if data.name is not None and data.name != app.name:
        conflict = db.execute(
            select(Application).where(
                Application.name == data.name,
                Application.tenant_id == user.tenant_id,
                Application.id != app_id,
            )
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una aplicación con ese nombre",
            )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(app, key, value)

    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(
    app_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Elimina una aplicación, sus lotes, páginas y ficheros en storage."""
    app = _get_app_or_404(app_id, user.tenant_id, db)
    image_paths = [
        page.image_path
        for batch in app.batches
        for page in batch.pages
        if page.image_path
    ]
    db.delete(app)
    db.commit()
    for path in image_paths:
        storage.delete(path)
