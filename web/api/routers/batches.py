"""Router CRUD de lotes (tenant-scoped)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.routers._helpers import ensure_batch_mutable, get_batch_for_tenant
from web.api.schemas.batch import (
    BatchCreate,
    BatchListItem,
    BatchResponse,
    BatchUpdate,
    ReorderBatchIn,
)
from web.api.schemas.pagination import (
    PageParams,
    PaginatedResponse,
    pagination_params,
)
from web.api.storage import StorageDep
from web.api.tasks.pipeline_runner import run_pipeline_for_batch
from web.api.tasks.transfer_runner import run_transfer_for_batch

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


@router.get("", response_model=PaginatedResponse[BatchListItem])
def list_batches(
    user: CurrentUser,
    db: SessionDep,
    application_id: int | None = Query(None),
    state: str | None = Query(None),
    page: PageParams = Depends(pagination_params),
):
    """Lista los lotes del tenant (paginado), filtrando por aplicación y estado."""
    base = select(Batch).where(Batch.tenant_id == user.tenant_id)
    if application_id is not None:
        base = base.where(Batch.application_id == application_id)
    if state is not None:
        base = base.where(Batch.state == state)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(
            base.order_by(Batch.created_at.desc()).limit(page.limit).offset(page.offset)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse[BatchListItem](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


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


@router.post("/{batch_id}/transfer", response_model=BatchResponse, status_code=202)
def transfer_batch(
    batch_id: int,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Dispara la transferencia del lote en background.

    El lote debe estar en estado ``read`` (pipeline completado). El estado
    real de la transferencia se notifica vía WebSocket
    ``/ws/batches/{batch_id}`` con eventos ``transfer_started``,
    ``transfer_page``, ``transfer_completed``, ``transfer_aborted`` o
    ``transfer_error``.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    if batch.state != "read":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no está listo para transferir",
        )

    background_tasks.add_task(
        run_transfer_for_batch,
        batch_id=batch.id,
        storage=storage,
    )
    return batch


@router.post("/{batch_id}/reorder", response_model=BatchResponse)
def reorder_batch(
    batch_id: int,
    payload: ReorderBatchIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Reordena las páginas del lote aplicando page_index = posición en la lista.

    - 404 si el lote no es del tenant.
    - 409 si el lote está en ejecución.
    - 422 si page_ids no coincide con el set actual de páginas.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="reordenar páginas")

    pages = db.execute(select(Page).where(Page.batch_id == batch_id)).scalars().all()
    existing_ids = {p.id for p in pages}
    requested = set(payload.page_ids)

    if existing_ids != requested or len(payload.page_ids) != len(existing_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_ids no coincide con el set actual de páginas del lote",
        )

    id_to_page = {p.id: p for p in pages}
    for idx, pid in enumerate(payload.page_ids):
        id_to_page[pid].page_index = idx

    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}/pages/after/{page_id}")
def delete_pages_from(
    batch_id: int,
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Elimina ``page_id`` y todas las páginas con ``page_index >= anchor.page_index``.

    - 404 si el lote no es del tenant.
    - 409 si el lote está en ejecución.
    - 404 si la página no pertenece al lote.
    """
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    ensure_batch_mutable(batch, action="eliminar páginas")

    anchor = db.query(Page).filter_by(id=page_id, batch_id=batch_id).first()
    if anchor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Página no encontrada en este lote",
        )

    to_delete = (
        db.query(Page)
        .filter(Page.batch_id == batch_id, Page.page_index >= anchor.page_index)
        .all()
    )
    deleted_count = len(to_delete)
    for p in to_delete:
        try:
            storage.delete(p.image_path)
        except Exception:
            log.warning("No se pudo borrar fichero %s", p.image_path)
        db.delete(p)

    db.flush()
    batch.page_count = db.query(Page).filter_by(batch_id=batch_id).count()
    db.commit()

    return {"deleted": deleted_count, "batch_page_count": batch.page_count}


def _safe_filename(name: str, fallback: str) -> str:
    """Sanitiza un nombre de fichero para incluirlo en el ZIP."""
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._-")
    return cleaned or fallback


@router.get("/{batch_id}/export")
def export_batch(
    batch_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Descarga el lote como ZIP con páginas + manifest.json."""
    import io
    import json
    import zipfile
    from pathlib import PurePosixPath

    from fastapi.responses import StreamingResponse

    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    pages = sorted(batch.pages, key=lambda p: p.page_index)

    buffer = io.BytesIO()
    used_names: set[str] = set()
    page_entries: list[dict] = []

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for page in pages:
            ext = PurePosixPath(page.image_path).suffix or ".bin"
            base = f"page_{page.page_index + 1:04d}"
            filename = f"{base}{ext}"
            n = 1
            while filename in used_names:
                n += 1
                filename = f"{base}_{n}{ext}"
            used_names.add(filename)

            try:
                content = storage.read(page.image_path)
            except FileNotFoundError:
                continue
            zf.writestr(f"pages/{filename}", content)

            try:
                fields = (
                    json.loads(page.index_fields_json) if page.index_fields_json else {}
                )
            except json.JSONDecodeError:
                fields = {}
            page_entries.append(
                {
                    "id": page.id,
                    "page_index": page.page_index,
                    "filename": f"pages/{filename}",
                    "ocr_text": page.ocr_text or "",
                    "fields": fields,
                    "needs_review": page.needs_review,
                    "review_reason": page.review_reason or "",
                    "is_blank": page.is_blank,
                    "pipeline_processed": page.pipeline_processed,
                    "barcodes": [
                        {
                            "value": b.value,
                            "symbology": b.symbology,
                            "role": b.role,
                            "pos": [b.pos_x, b.pos_y, b.pos_w, b.pos_h],
                        }
                        for b in page.barcodes
                    ],
                }
            )

        manifest = {
            "batch_id": batch.id,
            "application_id": batch.application_id,
            "state": batch.state,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
            "page_count": len(page_entries),
            "pages": page_entries,
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    buffer.seek(0)
    fname = _safe_filename(f"batch_{batch.id}", f"batch_{batch.id}") + ".zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
