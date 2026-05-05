"""Router de páginas — upload, listado, descarga y borrado (tenant-scoped)."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pymupdf
from PIL import Image
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.barcode import Barcode
from app.models.batch import Batch
from app.models.page import Page
from web.api.auth.dependencies import CurrentUser
from web.api.config import get_web_settings
from web.api.database import SessionDep
from web.api.routers._helpers import ensure_batch_mutable, get_batch_for_tenant
from web.api.routers.ws import broadcast_page_updated
from web.api.schemas.page import (
    AddBarcodeIn,
    BarcodeResponse,
    PageListItem,
    PagePatchIn,
    PageResponse,
    PageUploadResponse,
    RotatePageIn,
)
from web.api.storage import StorageDep

log = logging.getLogger(__name__)

router = APIRouter()

_SINGLE_IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "bmp"})
_TIFF_EXTS = frozenset({"tif", "tiff"})
_PDF_EXTS = frozenset({"pdf"})
_ALL_EXTS = _SINGLE_IMAGE_EXTS | _TIFF_EXTS | _PDF_EXTS
_MEDIA_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
}


def _get_page_in_batch_or_404(
    batch_id: int,
    page_id: int,
    tenant_id: int,
    db: Session,
) -> Page:
    """Obtiene una página dentro de un lote del tenant, o lanza 404."""
    get_batch_for_tenant(batch_id, tenant_id, db)
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


def _get_page_for_user(page_id: int, tenant_id: int, db: Session) -> Page:
    """Obtiene una página del tenant actual (join Page → Batch) o lanza 404.

    Helper independiente del batch_id en URL: valida tenant uniendo
    ``Page`` con ``Batch`` y filtrando por ``Batch.tenant_id``.
    """
    page = db.execute(
        select(Page)
        .join(Batch, Page.batch_id == Batch.id)
        .where(
            Page.id == page_id,
            Batch.tenant_id == tenant_id,
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


def _iter_pdf_pages_as_png(content: bytes, dpi: int) -> Iterator[bytes]:
    """Itera cada página de un PDF como bytes PNG (streaming)."""
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            yield pix.tobytes("png")
    finally:
        doc.close()


def _iter_tiff_frames_as_png(content: bytes) -> Iterator[bytes]:
    """Itera cada frame de un TIFF (single o multi-página) como bytes PNG.

    Convertir a PNG es necesario porque los navegadores no renderizan TIFF
    nativamente. Pillow soporta TIFF multi-página vía ``seek()``.
    """
    img = Image.open(io.BytesIO(content))
    try:
        while True:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            yield buf.getvalue()
            try:
                img.seek(img.tell() + 1)
            except EOFError:
                break
    finally:
        img.close()


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
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    settings = get_web_settings()

    next_idx = _next_page_index(batch_id, db)
    created: list[Page] = []

    def _persist_page(payload: bytes, payload_ext: str) -> None:
        nonlocal next_idx
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

    for upload in files:
        ext = _extract_extension(upload.filename)
        content = await upload.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichero vacío: '{upload.filename}'",
            )

        if ext in _PDF_EXTS:
            try:
                for png_bytes in _iter_pdf_pages_as_png(
                    content,
                    settings.storage.pdf_dpi,
                ):
                    _persist_page(png_bytes, "png")
            except Exception as e:
                log.warning("Error procesando PDF '%s': %s", upload.filename, e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF no válido: {upload.filename}",
                ) from e
        elif ext in _TIFF_EXTS:
            try:
                for png_bytes in _iter_tiff_frames_as_png(content):
                    _persist_page(png_bytes, "png")
            except Exception as e:
                log.warning("Error procesando TIFF '%s': %s", upload.filename, e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"TIFF no válido: {upload.filename}",
                ) from e
        else:
            _persist_page(content, ext)

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
    """Lista las páginas de un lote (ordenadas por page_index).

    Incluye `barcodes_count` por página para que el frontend pueda mostrar
    contadores agregados sin tener que cargar cada página individualmente.
    """
    get_batch_for_tenant(batch_id, user.tenant_id, db)
    rows = db.execute(
        select(Page, func.count(Barcode.id).label("barcodes_count"))
        .outerjoin(Barcode, Barcode.page_id == Page.id)
        .where(Page.batch_id == batch_id)
        .group_by(Page.id)
        .order_by(Page.page_index)
    ).all()
    items: list[PageListItem] = []
    for page, barcodes_count in rows:
        item = PageListItem.model_validate(page)
        item.barcodes_count = int(barcodes_count or 0)
        items.append(item)
    return items


@router.get(
    "/batches/{batch_id}/pages/{page_id}",
    response_model=PageResponse,
)
def get_page(
    batch_id: int,
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
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
    if not page.image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada en storage",
        )
    try:
        content = storage.read(page.image_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada en storage",
        )
    ext = page.image_path.rsplit(".", 1)[-1].lower()
    return Response(
        content=content,
        media_type=_MEDIA_TYPES.get(ext, "application/octet-stream"),
    )


@router.patch("/pages/{page_id}", response_model=PageResponse)
def patch_page(
    page_id: int,
    payload: PagePatchIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Actualiza flags de una página (is_excluded, needs_review, review_reason).

    Devuelve 404 si la página no existe o no pertenece al tenant.
    Devuelve 409 si el lote está en ejecución (``running`` o ``transferring``).
    """
    page = _get_page_for_user(page_id, user.tenant_id, db)
    ensure_batch_mutable(page.batch, action="editar página")

    if payload.is_excluded is not None:
        page.is_excluded = payload.is_excluded
    if payload.needs_review is not None:
        page.needs_review = payload.needs_review
        if not payload.needs_review:
            page.review_reason = ""
    if payload.review_reason is not None:
        page.review_reason = payload.review_reason

    db.commit()
    db.refresh(page)
    broadcast_page_updated(page.batch_id, page.id, "flags")
    return page


@router.post("/pages/{page_id}/rotate", response_model=PageResponse)
def rotate_page(
    page_id: int,
    payload: RotatePageIn,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Rota la imagen N×90° CW (destructivo) y actualiza coords de barcodes.

    Devuelve 404 si la página no existe o no pertenece al tenant.
    Devuelve 409 si el lote está en ejecución (``running`` o ``transferring``).
    Devuelve 422 si ``turns`` no está en {1, 2, 3} (validado por Pydantic).

    Orden de operaciones para mitigar atomicidad parcial: primero se calculan
    y persisten (flush) las nuevas coords de barcodes en BD; después se
    escribe la imagen rotada; finalmente se hace commit. Si el flush falla,
    la imagen queda intacta.
    """
    page = _get_page_for_user(page_id, user.tenant_id, db)
    ensure_batch_mutable(page.batch, action="rotar")

    # Leer imagen del storage (genérico: filesystem o MinIO)
    try:
        original_bytes = storage.read(page.image_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo leer la imagen del storage",
        ) from e

    # Rotar con Pillow (preserva DPI y formato; soporta PNG/JPEG/TIFF/BMP)
    ext = page.image_path.rsplit(".", 1)[-1].lower() if "." in page.image_path else "png"
    try:
        with Image.open(io.BytesIO(original_bytes)) as pil_img:
            pil_img.load()
            w, h = pil_img.size
            dpi = pil_img.info.get("dpi")
            # PIL.Image.ROTATE_270 = 90° CW (sentido horario en convención PIL)
            rotated = pil_img
            for _ in range(payload.turns):
                rotated = rotated.transpose(Image.Transpose.ROTATE_270)
            buf = io.BytesIO()
            save_kwargs: dict = {"format": rotated.format or pil_img.format or "PNG"}
            if dpi:
                save_kwargs["dpi"] = dpi
            rotated.save(buf, **save_kwargs)
            new_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo rotar la imagen",
        ) from e

    # 1. Calcular y aplicar coords barcodes (en memoria — pendiente flush).
    cur_h, cur_w = h, w
    for _ in range(payload.turns):
        for bc in page.barcodes:
            old_x, old_y, old_w, old_h = bc.pos_x, bc.pos_y, bc.pos_w, bc.pos_h
            bc.pos_x = cur_h - old_y - old_h
            bc.pos_y = old_x
            bc.pos_w = old_h
            bc.pos_h = old_w
        # Tras cada 90° CW, H y W se intercambian.
        cur_h, cur_w = cur_w, cur_h

    # 2. Flush a BD sin commit — si falla, imagen intacta.
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error persistiendo coords de barcodes",
        ) from e

    # 3. Subir imagen rotada como nuevo objeto y borrar el viejo (atomicidad
    # eventual: si la subida falla, la imagen original sigue en su sitio).
    try:
        old_path = page.image_path
        new_path = storage.save(
            tenant_id=user.tenant_id,
            batch_id=page.batch_id,
            content=new_bytes,
            extension=ext,
        )
        page.image_path = new_path
        try:
            storage.delete(old_path)
        except Exception:
            log.warning("No se pudo borrar la imagen vieja %s", old_path)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo escribir la imagen rotada",
        ) from e

    # 4. Commit final.
    db.commit()
    db.refresh(page)
    broadcast_page_updated(page.batch_id, page.id, "rotated")
    return page


@router.post("/pages/{page_id}/reprocess", response_model=PageResponse)
def reprocess_page(
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
) -> PageResponse:
    """Re-ejecuta el pipeline solo en esta página (síncrono).

    Útil para iterar sobre scripts durante desarrollo. Bloquea durante la
    ejecución y devuelve el PageResponse actualizado.

    - 404 si la página no existe o no pertenece al tenant.
    - 409 si el lote está en estado running/transferring.
    """
    from web.api.services.context_builders import build_app_context, build_batch_context
    from web.api.tasks.pipeline_runner import build_executor, process_page

    page = _get_page_for_user(page_id, user.tenant_id, db)
    batch = page.batch
    ensure_batch_mutable(batch, action="reprocesar página")

    executor, script_engine = build_executor(batch.application)
    try:
        app_ctx = build_app_context(batch.application)
        batch_ctx = build_batch_context(batch)
        process_page(page, executor, app_ctx, batch_ctx, storage, db)
        page.pipeline_processed = True
        db.commit()
        db.refresh(page)
    finally:
        script_engine.shutdown()

    return PageResponse.model_validate(page)


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
    deleted_page_id = page.id

    db.delete(page)
    batch = db.get(Batch, batch_id)
    if batch is not None:
        batch.page_count = max(0, batch.page_count - 1)
    db.commit()

    if image_path:
        storage.delete(image_path)

    broadcast_page_updated(batch_id, deleted_page_id, "deleted")


@router.post(
    "/pages/{page_id}/barcodes",
    response_model=BarcodeResponse,
    status_code=201,
)
def add_manual_barcode(
    page_id: int,
    payload: AddBarcodeIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Añade un barcode manual a la página.

    Devuelve 404 si la página no existe o no pertenece al tenant.
    Devuelve 409 si el lote está en ejecución (``running`` o ``transferring``).
    Devuelve 422 si el value está vacío (validado por Pydantic).
    """
    page = _get_page_for_user(page_id, user.tenant_id, db)
    ensure_batch_mutable(page.batch, action="añadir barcode")

    bc = Barcode(
        page_id=page.id,
        value=payload.value,
        symbology=payload.symbology,
        engine="manual",
        step_id="manual",
        quality=0.0,
        pos_x=0,
        pos_y=0,
        pos_w=0,
        pos_h=0,
        role="",
    )
    db.add(bc)
    db.commit()
    db.refresh(bc)
    broadcast_page_updated(
        page.batch_id,
        page.id,
        "barcode_added",
        extra={"barcode_id": bc.id},
    )
    return bc


@router.delete(
    "/pages/{page_id}/barcodes/{barcode_id}",
    status_code=204,
)
def delete_barcode(
    page_id: int,
    barcode_id: int,
    user: CurrentUser,
    db: SessionDep,
):
    """Elimina un barcode de la página.

    Devuelve 404 si la página no es del tenant del usuario, o si el barcode
    no pertenece a la página. Devuelve 409 si el lote está en ejecución.
    """
    page = _get_page_for_user(page_id, user.tenant_id, db)
    ensure_batch_mutable(page.batch, action="eliminar barcode")

    bc = next((b for b in page.barcodes if b.id == barcode_id), None)
    if bc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barcode no encontrado en esta página",
        )

    batch_id = page.batch_id
    page_id_local = page.id
    db.delete(bc)
    db.commit()
    broadcast_page_updated(
        batch_id,
        page_id_local,
        "barcode_deleted",
        extra={"barcode_id": barcode_id},
    )
    return Response(status_code=204)
