"""WebSocket endpoints para eventos en tiempo real.

Auth via query parameter ``?token=...`` (los clientes WS no pueden enviar
headers con WebSocket nativo de navegador). El token JWT se valida y se
comprueba que el ``tenant_id`` del usuario coincide con el del lote.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.models.batch import Batch
from web.api.auth.security import decode_access_token
from web.api.database import get_session_factory
from web.api.events import PipelineEvent, PipelineEventBus, get_event_bus
from web.api.models import User

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/batches/{batch_id}")
async def batch_events(
    websocket: WebSocket,
    batch_id: int,
    token: str = Query(...),
) -> None:
    """Stream de eventos del pipeline para un lote concreto."""
    user = _authenticate(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not _user_owns_batch(user, batch_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    bus = get_event_bus()
    bus.attach_loop(asyncio.get_running_loop())
    queue = bus.subscribe(batch_id)

    await websocket.accept()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.to_dict())
            if event.type in (
                "pipeline_completed",
                "pipeline_error",
                "transfer_completed",
                "transfer_error",
                "transfer_aborted",
            ):
                break
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(batch_id, queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass


def broadcast_page_updated(
    batch_id: int,
    page_id: int,
    action: str,
    extra: dict[str, Any] | None = None,
    event_bus: PipelineEventBus | None = None,
) -> None:
    """Publica un evento ``page_updated`` para los subscriptores del lote.

    Helper thread-safe: se usa desde endpoints HTTP síncronos (FastAPI los
    ejecuta en threadpool). Delega en ``PipelineEventBus.publish_from_thread``
    que internamente usa ``call_soon_threadsafe`` para entregar al loop
    del WebSocket sin condiciones de carrera.

    Args:
        batch_id: ID del lote (routing del evento).
        page_id: ID de la página afectada. Usar ``0`` para acciones que
            afectan a todo el lote (``reordered``, batch-level ``deleted``).
        action: ``"rotated"`` | ``"flags"`` | ``"barcode_added"`` |
            ``"barcode_deleted"`` | ``"deleted"`` | ``"reordered"``.
        extra: Campos adicionales a incluir en el payload (p.ej.
            ``{"barcode_id": 42}``).
        event_bus: Bus opcional (para tests). Si es ``None`` se usa el
            singleton.
    """
    bus = event_bus if event_bus is not None else get_event_bus()
    payload: dict[str, Any] = {"page_id": page_id, "action": action}
    if extra:
        payload.update(extra)
    bus.publish_from_thread(
        PipelineEvent(batch_id=batch_id, type="page_updated", payload=payload)
    )


def _authenticate(token: str) -> User | None:
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    factory = get_session_factory()
    with factory() as session:
        user = session.get(User, int(user_id))
        if user is None or not user.active:
            return None
        session.expunge(user)
        return user


def _user_owns_batch(user: User, batch_id: int) -> bool:
    factory = get_session_factory()
    with factory() as session:
        batch = session.get(Batch, batch_id)
        return batch is not None and batch.tenant_id == user.tenant_id
