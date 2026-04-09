"""Router de páginas — upload, listado, descarga y borrado (tenant-scoped)."""

from __future__ import annotations

import logging

import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.page import Page
from web.api.auth.dependencies import CurrentUser
from web.api.config import get_web_settings
from web.api.database import SessionDep
from web.api.schemas.page import (
    PageListItem,
    PageResponse,
    PageUploadResponse,
)
from web.api.storage import StorageDep

log = logging.getLogger(__name__)

router = APIRouter()

# Extensiones soportadas (minúsculas, sin punto)
_SINGLE_IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "bmp", "tif", "tiff"})
_PDF_EXTS = frozenset({"pdf"})
_ALL_EXTS = _SINGLE_IMAGE_EXTS | _PDF_EXTS


def _get_batch_or_404(batch_id: int, tenant_id: int, db: Session) -> Batch:
    """Obtiene un lote del tenant o lanza 404."""
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


def _get_page_in_batch_or_404(
    batch_id: int, page_id: int, tenant_id: int, db: Session,
) -> Page:
    """Obtiene una página dentro de un lote del tenant, o lanza 404."""
    _get_batch_or_404(batch_id, tenant_id, db)
    page = db.execute(
        select(Page).where(
            Page.id == page_id,
            Page.batch_id == batch_id,
        )
    ).scalar_one_or_none()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Página no encontrada",
        )
    return page


def _extract_extension(filename: str | None) -> str:
    """Obtiene la extensión en minúsculas (sin punto) desde el filename."""
    if not filename or "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero no tiene extensión",
        )
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in _ALL_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado: '{ext}'. Válidos: {sorted(_ALL_EXTS)}",
        )
    return ext


def _split_pdf_to_png_bytes(content: bytes, dpi: int) -> list[bytes]:
    """Convierte cada página de un PDF en bytes PNG."""
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        pages: list[bytes] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            pages.append(pix.tobytes("png"))
        return pages
    finally:
        doc.close()


def _next_page_index(batch_id: int, db: Session) -> int:
    """Devuelve el siguiente page_index libre para un lote."""
    max_idx = db.execute(
        select(func.max(Page.page_index)).where(Page.batch_id == batch_id)
    ).scalar()
    return 0 if max_idx is None else max_idx + 1


@router.post(
    "/batches/{batch_id}/pages",
    response_model=PageUploadResponse,
    status_code=201,
)
async def upload_pages(
    batch_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
    files: list[UploadFile] = File(...),
):
    """Sube uno o más ficheros a un lote, creando las páginas correspondientes.

    Las imágenes individuales crean una página cada una. Los PDFs se separan
    en tantas páginas como tenga el documento (a DPI configurable).
    """
    batch = _get_batch_or_404(batch_id, user.tenant_id, db)
    settings = get_web_settings()

    next_idx = _next_page_index(batch_id, db)
    created: list[Page] = []

    for upload in files:
        ext = _extract_extension(upload.filename)
        content = await upload.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichero vacío: '{upload.filename}'",
            )

        # Generar una lista de (bytes, ext) — una entrada por página lógica
        if ext in _PDF_EXTS:
            try:
                page_contents = _split_pdf_to_png_bytes(
                    content, settings.storage.pdf_dpi,
                )
            except Exception as e:
                log.warning("Error procesando PDF '%s': %s", upload.filename, e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF no válido: {upload.filename}",
                ) from e
            entries = [(b, "png") for b in page_contents]
        else:
            entries = [(content, ext)]

        for payload, payload_ext in entries:
            relative = storage.save(
                tenant_id=user.tenant_id,
                batch_id=batch_id,
                content=payload,
                extension=payload_ext,
            )
            page = Page(
                batch_id=batch_id,
                page_index=next_idx,
                image_path=relative,
            )
            db.add(page)
            created.append(page)
            next_idx += 1

    batch.page_count = next_idx
    db.commit()
    for page in created:
        db.refresh(page)

    return PageUploadResponse(
        created=[PageResponse.model_validate(p) for p in created],
        batch_page_count=batch.page_count,
    )


@router.get(
    "/batches/{batch_id}/pages",
    response_model=list[PageListItem],
)
def list_pages(batch_id: int, user: CurrentUser, db: SessionDep):
    """Lista las páginas de un lote (ordenadas por page_index)."""
    _get_batch_or_404(batch_id, user.tenant_id, db)
    pages = db.execute(
        select(Page)
        .where(Page.batch_id == batch_id)
        .order_by(Page.page_index)
    ).scalars().all()
    return pages


@router.get(
    "/batches/{batch_id}/pages/{page_id}",
    response_model=PageResponse,
)
def get_page(
    batch_id: int, page_id: int, user: CurrentUser, db: SessionDep,
):
    """Obtiene los metadatos de una página."""
    return _get_page_in_batch_or_404(batch_id, page_id, user.tenant_id, db)


@router.get("/batches/{batch_id}/pages/{page_id}/image")
def get_page_image(
    batch_id: int,
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Devuelve el fichero binario de la imagen de una página."""
    page = _get_page_in_batch_or_404(batch_id, page_id, user.tenant_id, db)
    if not page.image_path or not storage.exists(page.image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada en storage",
        )
    return FileResponse(storage.absolute_path(page.image_path))


@router.delete(
    "/batches/{batch_id}/pages/{page_id}",
    status_code=204,
)
def delete_page(
    batch_id: int,
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Elimina una página y su fichero de imagen asociado."""
    page = _get_page_in_batch_or_404(batch_id, page_id, user.tenant_id, db)
    image_path = page.image_path

    db.delete(page)
    # Actualizar page_count del lote
    batch = db.get(Batch, batch_id)
    if batch is not None:
        batch.page_count = max(0, batch.page_count - 1)
    db.commit()

    if image_path:
        storage.delete(image_path)
