"""Recuperación de lotes huérfanos.

Si el API o el worker se reinician en mitad de una ejecución de pipeline o
transferencia, los lotes pueden quedar en estado ``running`` o
``transferring`` indefinidamente. Esta función los detecta y los marca
``error_read`` (para pipeline) o ``error_read`` (para transferencia, mismo
estado terminal de error que usan los runners).

Se invoca desde el ``recovery_job`` del worker ARQ, que se enrola al
arrancar el lifespan del API.
"""

from __future__ import annotations

import logging

from sqlalchemy import update

from app.models.batch import Batch
from web.api.database import get_session_factory

log = logging.getLogger(__name__)

_STUCK_STATES = ("running", "transferring")


def recover_stuck_batches() -> int:
    """Marca como ``error_read`` todos los batches en estado huérfano.

    Returns:
        Número de batches recuperados.
    """
    factory = get_session_factory()
    with factory() as session:
        stmt = (
            update(Batch)
            .where(Batch.state.in_(_STUCK_STATES))
            .values(state="error_read")
        )
        result = session.execute(stmt)
        session.commit()
        n = result.rowcount or 0
        if n > 0:
            log.warning("Recovery: %d batches huérfanos marcados error_read", n)
        return n
