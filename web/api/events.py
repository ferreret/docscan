"""Event bus in-process para eventos de pipeline.

El runner se ejecuta como BackgroundTask de FastAPI (síncrono, en threadpool),
pero los consumidores son corrutinas de WebSocket en el event loop principal.
Este bus puentea ambos mundos:

- ``publish_from_thread`` se invoca desde el runner sync y programa la entrega
  en el loop vía ``call_soon_threadsafe``.
- ``subscribe`` entrega una ``asyncio.Queue`` que consume el handler WS.

Los eventos se filtran por ``batch_id``. Suscripciones sin consumir se
descartan en cuanto el cliente desconecta (via ``unsubscribe``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineEvent:
    """Evento publicado durante la ejecución de un pipeline."""

    batch_id: int
    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "batch_id": self.batch_id, **self.payload}


class PipelineEventBus:
    """Pub/sub en memoria por batch_id, thread-safe.

    El loop de asyncio se captura en construcción; los publicadores sync
    usan ``call_soon_threadsafe`` para entregar sin condiciones de carrera.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self._subscribers: dict[int, set[asyncio.Queue[PipelineEvent]]] = {}

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Asocia un loop. Llamado en ``lifespan`` de FastAPI."""
        self._loop = loop

    def subscribe(self, batch_id: int) -> asyncio.Queue[PipelineEvent]:
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self._subscribers.setdefault(batch_id, set()).add(queue)
        return queue

    def unsubscribe(self, batch_id: int, queue: asyncio.Queue[PipelineEvent]) -> None:
        subs = self._subscribers.get(batch_id)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(batch_id, None)

    def publish_from_thread(self, event: PipelineEvent) -> None:
        """Publica desde código síncrono (BackgroundTask en threadpool)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._dispatch, event)

    def _dispatch(self, event: PipelineEvent) -> None:
        for queue in list(self._subscribers.get(event.batch_id, ())):
            queue.put_nowait(event)


_bus: PipelineEventBus | None = None


def get_event_bus() -> PipelineEventBus:
    """Devuelve el bus singleton, creándolo si hace falta."""
    global _bus
    if _bus is None:
        _bus = PipelineEventBus()
    return _bus


def reset_event_bus() -> None:
    """Resetea el bus (para tests)."""
    global _bus
    _bus = None
