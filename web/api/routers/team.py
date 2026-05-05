"""Router de gestión de equipo: usuarios del tenant + invitaciones.

Todos los endpoints exigen rol ``company_admin`` (excepto
``accept-invitation`` que es público, y ``GET /users/me`` que cualquier
usuario puede consultar — ese último vive ya en auth).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from web.api.auth.dependencies import CurrentUser, require_role
from web.api.auth.security import hash_password
from web.api.database import SessionDep
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_OPERATOR,
    Invitation,
    User,
)
from web.api.schemas.pagination import (
    PageParams,
    PaginatedResponse,
    pagination_params,
)
from web.api.schemas.team import (
    AcceptInvitationRequest,
    InvitationCreate,
    InvitationResponse,
    UserListItem,
    UserUpdate,
)

router = APIRouter()

_INVITATION_TTL_DAYS = 7
_ASSIGNABLE_ROLES = (ROLE_COMPANY_ADMIN, ROLE_OPERATOR)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------
# Usuarios del tenant
# ---------------------------------------------------------------------


@router.get("/users", response_model=PaginatedResponse[UserListItem])
def list_users(
    user: CurrentUser,
    db: SessionDep,
    page: PageParams = Depends(pagination_params),
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    base = select(User).where(User.tenant_id == user.tenant_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(base.order_by(User.created_at).limit(page.limit).offset(page.offset))
        .scalars()
        .all()
    )
    return PaginatedResponse[UserListItem](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


def _get_tenant_user_or_404(user_id: int, tenant_id: int, db) -> User:
    u = db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return u


def _count_other_active_admins(tenant_id: int, exclude_user_id: int, db) -> int:
    """Cuenta company_admins activos del tenant, excluyendo a ``exclude_user_id``."""
    return db.execute(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id,
            User.role == ROLE_COMPANY_ADMIN,
            User.active.is_(True),
            User.id != exclude_user_id,
        )
    ).scalar_one()


_LAST_ADMIN_MSG = "El tenant debe mantener al menos un company_admin activo"


@router.patch("/users/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    data: UserUpdate,
    user: CurrentUser,
    db: SessionDep,
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    target = _get_tenant_user_or_404(user_id, user.tenant_id, db)

    if data.role is not None:
        if data.role not in _ASSIGNABLE_ROLES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Rol inválido. Debe ser uno de: {_ASSIGNABLE_ROLES}",
            )
        # Bloquear cambio de rol propio: el admin se quedaría atrapado como
        # operator (no puede revertirse) y, si era el único admin, el tenant
        # se quedaría sin company_admins.
        if target.id == user.id and data.role != target.role:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "No puedes cambiar tu propio rol",
            )
        # Proteger último admin: si bajamos un admin a operator y no quedan
        # otros admins activos en el tenant, rechazar.
        if (
            target.role == ROLE_COMPANY_ADMIN
            and data.role != ROLE_COMPANY_ADMIN
            and target.active
            and _count_other_active_admins(user.tenant_id, target.id, db) == 0
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, _LAST_ADMIN_MSG)
        target.role = data.role

    if data.active is not None:
        if target.id == user.id and not data.active:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "No puedes desactivar tu propia cuenta",
            )
        # Proteger último admin: si desactivamos al único admin activo del
        # tenant, rechazar.
        if (
            not data.active
            and target.role == ROLE_COMPANY_ADMIN
            and target.active
            and _count_other_active_admins(user.tenant_id, target.id, db) == 0
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, _LAST_ADMIN_MSG)
        target.active = data.active

    if data.display_name is not None:
        target.display_name = data.display_name

    db.commit()
    db.refresh(target)
    return target


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    user: CurrentUser,
    db: SessionDep,
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    if user_id == user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No puedes eliminar tu propia cuenta",
        )
    target = _get_tenant_user_or_404(user_id, user.tenant_id, db)
    # Proteger último admin: si el target es el único admin activo del
    # tenant, no permitir borrarlo.
    if (
        target.role == ROLE_COMPANY_ADMIN
        and target.active
        and _count_other_active_admins(user.tenant_id, target.id, db) == 0
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, _LAST_ADMIN_MSG)
    db.delete(target)
    db.commit()


# ---------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------


@router.get("/invitations", response_model=PaginatedResponse[InvitationResponse])
def list_invitations(
    user: CurrentUser,
    db: SessionDep,
    page: PageParams = Depends(pagination_params),
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    base = select(Invitation).where(
        Invitation.tenant_id == user.tenant_id,
        Invitation.accepted_at.is_(None),
    )
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(
            base.order_by(Invitation.created_at.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse[InvitationResponse](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    data: InvitationCreate,
    user: CurrentUser,
    db: SessionDep,
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    if data.role not in _ASSIGNABLE_ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Rol inválido. Debe ser uno de: {_ASSIGNABLE_ROLES}",
        )

    existing_user = db.execute(
        select(User).where(User.email == str(data.email))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un usuario con ese email",
        )

    token = secrets.token_urlsafe(48)
    inv = Invitation(
        tenant_id=user.tenant_id,
        email=str(data.email),
        role=data.role,
        token=token,
        expires_at=_now() + timedelta(days=_INVITATION_TTL_DAYS),
        created_by_user_id=user.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: int,
    user: CurrentUser,
    db: SessionDep,
    _admin=require_role(ROLE_COMPANY_ADMIN),
):
    inv = db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.tenant_id == user.tenant_id,
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitación no encontrada")
    db.delete(inv)
    db.commit()


@router.post("/invitations/accept", response_model=UserListItem)
def accept_invitation(data: AcceptInvitationRequest, db: SessionDep):
    """Endpoint público: crea el usuario asociado a una invitación válida."""
    inv = db.execute(
        select(Invitation).where(Invitation.token == data.token)
    ).scalar_one_or_none()

    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitación no válida")
    if inv.accepted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitación ya utilizada")
    if inv.expires_at < _now():
        raise HTTPException(status.HTTP_410_GONE, "Invitación expirada")

    existing_user = db.execute(
        select(User).where(User.email == inv.email)
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un usuario con ese email",
        )

    new_user = User(
        tenant_id=inv.tenant_id,
        email=inv.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=inv.role,
        active=True,
    )
    db.add(new_user)
    inv.accepted_at = _now()
    db.commit()
    db.refresh(new_user)
    return new_user
