"""Router para eventos lifecycle del workbench web."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.routers._helpers import get_batch_for_tenant
from web.api.schemas.event import EventFireIn, EventResult
from web.api.services.event_dispatcher import (
    EVENTS_REQUIRING_PAGE_ID,
    SUPPORTED_EVENTS,
    dispatch_event,
)
from app.models.page import Page

router = APIRouter()


@router.post(
    "/{batch_id}/events/{event_name}",
    response_model=EventResult,
)
def fire_event(
    batch_id: int,
    event_name: str,
    payload: EventFireIn,
    user: CurrentUser,
    db: SessionDep,
) -> EventResult:
    """Ejecuta un evento lifecycle del workbench.

    - 404 si el lote no es del tenant.
    - 400 si ``event_name`` no es uno de los soportados.
    - 422 si faltan campos requeridos (``page_id`` para navegación/page_changed;
      ``key`` para on_key_event).
    - 404 si el ``page_id`` no pertenece al lote.
    - 200 con ``executed=false`` si el script no está definido.
    """
    if event_name not in SUPPORTED_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Evento no soportado: {event_name}",
        )

    if event_name in EVENTS_REQUIRING_PAGE_ID and payload.page_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"page_id es requerido para {event_name}",
        )

    if event_name == "on_key_event" and not payload.key:
        raise HTTPException(
            status_code=422,
            detail="key es requerido para on_key_event",
        )

    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    page: Page | None = None
    if payload.page_id is not None:
        page = (
            db.query(Page)
            .filter(Page.id == payload.page_id, Page.batch_id == batch_id)
            .first()
        )
        if page is None:
            raise HTTPException(
                status_code=404,
                detail="Página no pertenece al lote",
            )

    return dispatch_event(
        event_name=event_name,
        application=batch.application,
        batch=batch,
        page=page,
        key=payload.key,
        extra=payload.extra,
        session=db,
    )
