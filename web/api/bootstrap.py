"""CLI de bootstrap inicial de la plataforma DocScan SaaS.

Crea (o reutiliza) el tenant ``TecnoMedia`` y un usuario con rol
``superadmin``. Idempotente: ejecutarlo varias veces con los mismos
argumentos no produce duplicados ni cambia el estado.

Uso:

    python -m web.api.bootstrap superadmin \
        --email admin@tecnomedia.es \
        --password ********** \
        --display "Admin TecnoMedia"
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

import web.api._register_models  # noqa: F401  registra todas las tablas
from web.api.auth.security import hash_password
from web.api.models import ROLE_SUPERADMIN, Tenant, User

logger = logging.getLogger(__name__)

TECNOMEDIA_TENANT_NAME = "TecnoMedia"
TECNOMEDIA_TENANT_SLUG = "tecnomedia"
TECNOMEDIA_TENANT_PLAN = "enterprise"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN = 8


class BootstrapError(Exception):
    """Error de validación durante el bootstrap inicial."""


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise BootstrapError(f"email no válido: {email!r}")


def _validate_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        raise BootstrapError(
            f"contraseña demasiado corta (mínimo {_MIN_PASSWORD_LEN} caracteres)"
        )


def _get_or_create_tecnomedia_tenant(db: Session) -> Tenant:
    """Devuelve el tenant TecnoMedia, creándolo si no existe."""
    tenant = db.execute(
        select(Tenant).where(Tenant.slug == TECNOMEDIA_TENANT_SLUG)
    ).scalar_one_or_none()
    if tenant is not None:
        return tenant
    tenant = Tenant(
        name=TECNOMEDIA_TENANT_NAME,
        slug=TECNOMEDIA_TENANT_SLUG,
        plan=TECNOMEDIA_TENANT_PLAN,
        active=True,
    )
    db.add(tenant)
    db.flush()
    logger.info("Tenant TecnoMedia creado (id=%s)", tenant.id)
    return tenant


def bootstrap_superadmin(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Crea (o reutiliza) tenant TecnoMedia y un superadmin con ``email``.

    Idempotente: si ya existe un usuario con ese email pertenecien-
    do al tenant TecnoMedia y con rol ``superadmin``, lo devuelve
    sin modificarlo.

    Args:
        db: Sesión SQLAlchemy abierta.
        email: Correo del superadmin.
        password: Contraseña en claro (mínimo 8 caracteres). Se hashea con bcrypt.
        display_name: Nombre visible del superadmin.

    Returns:
        El ``User`` creado o reutilizado.

    Raises:
        BootstrapError: si el email es inválido, la contraseña es corta,
            o el email pertenece a otro usuario que no es superadmin de
            TecnoMedia.
    """
    _validate_email(email)
    _validate_password(password)

    tenant = _get_or_create_tecnomedia_tenant(db)

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        if existing.tenant_id == tenant.id and existing.role == ROLE_SUPERADMIN:
            logger.info(
                "Superadmin con email %s ya existe (id=%s); no se modifica",
                email,
                existing.id,
            )
            return existing
        raise BootstrapError(
            f"el email {email!r} ya está en uso por otro usuario "
            "que no es superadmin de TecnoMedia"
        )

    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name,
        role=ROLE_SUPERADMIN,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Superadmin %s creado (id=%s)", email, user.id)
    return user


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parser CLI para ``python -m web.api.bootstrap``."""
    parser = argparse.ArgumentParser(
        prog="python -m web.api.bootstrap",
        description="Bootstrap inicial de la plataforma DocScan SaaS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sa = sub.add_parser(
        "superadmin",
        help="Crea (o reutiliza) el tenant TecnoMedia y un superadmin.",
    )
    sa.add_argument("--email", required=True, help="Email del superadmin")
    sa.add_argument(
        "--password", required=True, help="Contraseña (mínimo 8 caracteres)"
    )
    sa.add_argument("--display", required=True, help="Nombre visible")

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Devuelve el código de salida."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    args = parse_args(argv)

    if args.command == "superadmin":
        from web.api.database import get_session_factory

        factory = get_session_factory()
        with factory() as db:
            try:
                user = bootstrap_superadmin(
                    db,
                    email=args.email,
                    password=args.password,
                    display_name=args.display,
                )
            except BootstrapError as exc:
                logger.error("%s", exc)
                return 2
            print(
                f"OK: superadmin id={user.id} "
                f"email={user.email} tenant_id={user.tenant_id}"
            )
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
