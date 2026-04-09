"""Router CRUD de lotes (tenant-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.routers._helpers import get_batch_for_tenant
from web.api.schemas.batch import (
    BatchCreate,
    BatchListItem,
    BatchResponse,
    BatchUpdate,
)
from web.api.storage import StorageDep
from web.api.tasks.pipeline_runner import run_pipeline_for_batch

router = APIRouter()


def _assert_application_in_tenant(
    application_id: int,
    tenant_id: int,
    db: Session,
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
    return get_batch_for_tenant(batch_id, user.tenant_id, db)


@router.patch("/{batch_id}", response_model=BatchResponse)
def update_batch(
    batch_id: int,
    data: BatchUpdate,
    user: CurrentUser,
    db: SessionDep,
):
    """Actualiza un lote existente (estado, contadores, metadatos)."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(batch, key, value)

    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}", status_code=204)
def delete_batch(
    batch_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Elimina un lote, sus páginas y los ficheros asociados en storage."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    image_paths = [p.image_path for p in batch.pages if p.image_path]
    db.delete(batch)
    db.commit()
    for path in image_paths:
        storage.delete(path)


@router.post("/{batch_id}/run", response_model=BatchResponse, status_code=202)
def run_batch_pipeline(
    batch_id: int,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Dispara la ejecución del pipeline sobre todas las páginas del lote.

    Rechaza si el lote no tiene páginas. Delega la ejecución real a un
    BackgroundTask de FastAPI; el lote queda en su estado actual hasta que
    el background task lo actualiza a ``read`` o ``error_read``.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    if batch.page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no tiene páginas para procesar",
        )

    background_tasks.add_task(
        run_pipeline_for_batch,
        batch_id=batch.id,
        storage=storage,
    )
    return batch
