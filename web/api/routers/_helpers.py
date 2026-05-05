"""Helpers compartidos entre routers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.batch import Batch


def get_batch_for_tenant(batch_id: int, tenant_id: int, db: Session) -> Batch:
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


def ensure_batch_mutable(batch: Batch, action: str = "modificar") -> None:
    """Rechaza mutaciones si el lote está en ejecución.

    Lanza 409 si ``batch.state`` ∈ {"running", "transferring"}.
    """
    if batch.state in ("running", "transferring"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede {action} mientras el lote está en ejecución",
        )
