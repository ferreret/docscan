"""Router CRUD de lotes (tenant-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.schemas.batch import (
    BatchCreate,
    BatchListItem,
    BatchResponse,
    BatchUpdate,
)

router = APIRouter()


def _get_batch_or_404(batch_id: int, tenant_id: int, db: Session) -> Batch:
    """Obtiene un lote del tenant actual o lanza 404."""
    batch = db.execute(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado",
        )
    return batch


def _assert_application_in_tenant(
    application_id: int, tenant_id: int, db: Session,
) -> None:
    """Verifica que la aplicación pertenece al tenant, si no 404."""
    app = db.execute(
        select(Application.id).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicación no encontrada",
        )


@router.get("", response_model=list[BatchListItem])
def list_batches(
    user: CurrentUser,
    db: SessionDep,
    application_id: int | None = Query(None),
    state: str | None = Query(None),
):
    """Lista los lotes del tenant, filtrando opcionalmente por aplicación y estado."""
    stmt = select(Batch).where(Batch.tenant_id == user.tenant_id)
    if application_id is not None:
        stmt = stmt.where(Batch.application_id == application_id)
    if state is not None:
        stmt = stmt.where(Batch.state == state)
    stmt = stmt.order_by(Batch.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.post("", response_model=BatchResponse, status_code=201)
def create_batch(data: BatchCreate, user: CurrentUser, db: SessionDep):
    """Crea un nuevo lote en una aplicación del tenant del usuario."""
    _assert_application_in_tenant(data.application_id, user.tenant_id, db)

    batch = Batch(
        application_id=data.application_id,
        tenant_id=user.tenant_id,
        folder_path=data.folder_path,
        fields_json=data.fields_json,
        state="created",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch(batch_id: int, user: CurrentUser, db: SessionDep):
    """Obtiene un lote por ID."""
    return _get_batch_or_404(batch_id, user.tenant_id, db)


@router.patch("/{batch_id}", response_model=BatchResponse)
def update_batch(
    batch_id: int, data: BatchUpdate, user: CurrentUser, db: SessionDep,
):
    """Actualiza un lote existente (estado, contadores, metadatos)."""
    batch = _get_batch_or_404(batch_id, user.tenant_id, db)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(batch, key, value)

    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}", status_code=204)
def delete_batch(batch_id: int, user: CurrentUser, db: SessionDep):
    """Elimina un lote y todas sus páginas asociadas."""
    batch = _get_batch_or_404(batch_id, user.tenant_id, db)
    db.delete(batch)
    db.commit()
