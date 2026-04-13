"""WebSocket endpoints para eventos en tiempo real.

Auth via query parameter ``?token=...`` (los clientes WS no pueden enviar
headers con WebSocket nativo de navegador). El token JWT se valida y se
comprueba que el ``tenant_id`` del usuario coincide con el del lote.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.models.batch import Batch
from web.api.auth.security import decode_access_token
from web.api.database import get_session_factory
from web.api.events import get_event_bus
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
            if event.type in ("pipeline_completed", "pipeline_error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(batch_id, queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass


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
