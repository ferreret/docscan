"""Router ``/api/admin/users`` — gestión de usuarios cross-tenant por superadmin.

Solo accesible con rol ``superadmin``. Todas las mutaciones se
registran en ``audit_logs`` (hito 6 del sprint superadmin).

Guards:
- No puedes degradar/desactivar/borrar al último superadmin global.
- No puedes degradar/desactivar/borrar al último company_admin activo
  de un tenant cuando ese tenant aún tiene usuarios.
- No puedes modificar tu propia cuenta desde aquí (defense-in-depth).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from web.api.audit import audit
from web.api.auth.dependencies import CurrentUser, require_role
from web.api.auth.security import hash_password
from web.api.database import SessionDep
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_SUPERADMIN,
    Tenant,
    User,
)
from web.api.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserListItem,
    AdminUserUpdateRequest,
)
from web.api.schemas.pagination import (
    PageParams,
    PaginatedResponse,
    pagination_params,
)

log = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _to_admin_item(user: User, tenant: Tenant | None) -> AdminUserListItem:
    return AdminUserListItem(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        active=user.active,
        created_at=user.created_at,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant is not None else "",
    )


def _get_user_or_404(user_id: int, db) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return u


def _count_other_active_superadmins(db, exclude_user_id: int) -> int:
    return db.execute(
        select(func.count(User.id)).where(
            User.role == ROLE_SUPERADMIN,
            User.active.is_(True),
            User.id != exclude_user_id,
        )
    ).scalar_one()


def _count_other_active_company_admins(db, tenant_id: int, exclude_user_id: int) -> int:
    return db.execute(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id,
            User.role == ROLE_COMPANY_ADMIN,
            User.active.is_(True),
            User.id != exclude_user_id,
        )
    ).scalar_one()


_LAST_SUPERADMIN_MSG = "La plataforma debe mantener al menos un superadmin activo"
_LAST_COMPANY_ADMIN_MSG = "El tenant debe mantener al menos un company_admin activo"
_SELF_MSG = (
    "No puedes modificar tu propia cuenta desde /admin/users; "
    "usa /api/users (team) o pide a otro superadmin"
)


def _check_demote_or_deactivate(
    db, target: User, *, becoming_active: bool, becoming_role: str
) -> None:
    """Aplica los guards de "último superadmin/company_admin"."""
    losing_super = (
        target.role == ROLE_SUPERADMIN
        and target.active
        and (becoming_role != ROLE_SUPERADMIN or not becoming_active)
    )
    if losing_super and _count_other_active_superadmins(db, target.id) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, _LAST_SUPERADMIN_MSG)

    losing_company_admin = (
        target.role == ROLE_COMPANY_ADMIN
        and target.active
        and (becoming_role != ROLE_COMPANY_ADMIN or not becoming_active)
    )
    if (
        losing_company_admin
        and _count_other_active_company_admins(db, target.tenant_id, target.id) == 0
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, _LAST_COMPANY_ADMIN_MSG)


# --------------------------------------------------------------------
# List
# --------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[AdminUserListItem])
def list_users(
    user: CurrentUser,
    db: SessionDep,
    tenant_id: int | None = None,
    page: PageParams = Depends(pagination_params),
    _sa=require_role(ROLE_SUPERADMIN),
):
    base = select(User)
    if tenant_id is not None:
        base = base.where(User.tenant_id == tenant_id)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    rows = (
        db.execute(
            base.order_by(User.created_at.desc()).limit(page.limit).offset(page.offset)
        )
        .scalars()
        .all()
    )
    # Resolver tenant_name por usuario (joineado a mano para mantener simple).
    tenant_ids = {u.tenant_id for u in rows}
    tenants = (
        db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids))).scalars().all()
        if tenant_ids
        else []
    )
    by_id = {t.id: t for t in tenants}
    items = [_to_admin_item(u, by_id.get(u.tenant_id)) for u in rows]
    return PaginatedResponse[AdminUserListItem](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


# --------------------------------------------------------------------
# Create
# --------------------------------------------------------------------


@router.post(
    "",
    response_model=AdminUserListItem,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: AdminUserCreateRequest,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    tenant = db.get(Tenant, data.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant no encontrado")

    if (
        db.execute(
            select(User).where(User.email == str(data.email))
        ).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email"
        )

    new_user = User(
        tenant_id=tenant.id,
        email=str(data.email),
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        active=True,
    )
    db.add(new_user)
    db.flush()

    audit(
        db,
        actor=user,
        action="user.created",
        target_type="user",
        target_id=new_user.id,
        payload={
            "email": str(data.email),
            "role": data.role,
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
        },
    )
    db.commit()
    db.refresh(new_user)
    return _to_admin_item(new_user, tenant)


# --------------------------------------------------------------------
# Update
# --------------------------------------------------------------------


@router.patch("/{user_id}", response_model=AdminUserListItem)
def update_user(
    user_id: int,
    data: AdminUserUpdateRequest,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    target = _get_user_or_404(user_id, db)
    if target.id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, _SELF_MSG)

    changes: dict[str, dict[str, object]] = {}

    new_role = data.role if data.role is not None else target.role
    new_active = data.active if data.active is not None else target.active

    if data.role is not None and data.role != target.role:
        _check_demote_or_deactivate(
            db, target, becoming_active=new_active, becoming_role=new_role
        )
        changes["role"] = {"from": target.role, "to": data.role}
        target.role = data.role

    if data.active is not None and data.active != target.active:
        _check_demote_or_deactivate(
            db, target, becoming_active=new_active, becoming_role=new_role
        )
        changes["active"] = {"from": target.active, "to": data.active}
        target.active = data.active

    if data.display_name is not None and data.display_name != target.display_name:
        changes["display_name"] = {
            "from": target.display_name,
            "to": data.display_name,
        }
        target.display_name = data.display_name

    if changes:
        audit(
            db,
            actor=user,
            action="user.updated",
            target_type="user",
            target_id=target.id,
            payload={"changes": changes, "tenant_id": target.tenant_id},
        )

    db.commit()
    db.refresh(target)
    tenant = db.get(Tenant, target.tenant_id)
    return _to_admin_item(target, tenant)


# --------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    target = _get_user_or_404(user_id, db)
    if target.id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, _SELF_MSG)

    # Borrar = becoming_active=False con cualquier rol no relevante.
    _check_demote_or_deactivate(
        db, target, becoming_active=False, becoming_role=target.role
    )

    snapshot = {
        "email": target.email,
        "role": target.role,
        "tenant_id": target.tenant_id,
    }
    audit(
        db,
        actor=user,
        action="user.deleted",
        target_type="user",
        target_id=target.id,
        payload=snapshot,
    )

    db.delete(target)
    db.commit()
