"""Helper para registrar acciones administrativas en ``audit_logs``.

Lo consumen los routers ``/api/admin/...`` y, opcionalmente, tareas
internas (cron, recovery). El llamador es responsable del commit.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from web.api.models import AuditLog, User


def audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: int | None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Registra una entrada en ``audit_logs``.

    Args:
        db: Sesión SQLAlchemy abierta.
        actor: Usuario que ejecuta la acción. ``None`` para acciones de
            sistema (cron, recovery). Cuando es no ``None``, su
            ``tenant_id`` se copia al registro.
        action: Código corto de la acción (``"tenant.created"``,
            ``"user.deleted"``, ``"tenant.suspended"``, ...).
        target_type: Tipo del objeto afectado (``"tenant"``, ``"user"``,
            ``"batch"``, ...).
        target_id: Identificador del objeto, o ``None`` si no aplica
            (p. ej. ``login.failed`` con email inexistente).
        payload: Datos adicionales serializables a JSON (campos modi-
            ficados, motivo, etc.). Por defecto ``{}``.

    Returns:
        El ``AuditLog`` creado y añadido a la sesión.

    Note:
        El helper solo hace ``add`` + ``flush``. El ``commit`` lo
        decide el llamador para mantener atomicidad con la operación
        que registra.
    """
    entry = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        tenant_id=actor.tenant_id if actor is not None else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload_json=json.dumps(payload or {}),
    )
    db.add(entry)
    db.flush()
    return entry
