"""Router ``/api/admin/tenants`` — gestión de tenants por superadmin.

Solo accesible con rol ``superadmin``. Cada acción de mutación se
registra en ``audit_logs`` (hitos 4 y 5 del sprint superadmin).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from web.api.audit import audit
from web.api.auth.dependencies import CurrentUser, require_role
from web.api.auth.security import hash_password
from web.api.bootstrap import TECNOMEDIA_TENANT_SLUG
from web.api.database import SessionDep
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_SUPERADMIN,
    Invitation,
    Tenant,
    User,
)
from web.api.schemas.admin import (
    TenantCreateRequest,
    TenantDetail,
    TenantListItem,
    TenantStats,
    TenantUpdateRequest,
    TenantUserItem,
)
from web.api.schemas.pagination import (
    PageParams,
    PaginatedResponse,
    pagination_params,
)
from web.api.storage import StorageDep

log = logging.getLogger(__name__)

router = APIRouter()

_BATCH_ACTIVE_STATES = ("running", "transferring")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "tenant"


def _stats_for_tenant(db, tenant_id: int) -> TenantStats:
    n_users = db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    ).scalar_one()
    n_apps = db.execute(
        select(func.count(Application.id)).where(Application.tenant_id == tenant_id)
    ).scalar_one()
    n_batches = db.execute(
        select(func.count(Batch.id)).where(Batch.tenant_id == tenant_id)
    ).scalar_one()
    return TenantStats(n_users=n_users, n_applications=n_apps, n_batches=n_batches)


def _to_list_item(tenant: Tenant, db) -> TenantListItem:
    return TenantListItem(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        active=tenant.active,
        created_at=tenant.created_at,
        stats=_stats_for_tenant(db, tenant.id),
    )


def _get_tenant_or_404(tenant_id: int, db) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant no encontrado")
    return tenant


# --------------------------------------------------------------------
# List
# --------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[TenantListItem])
def list_tenants(
    user: CurrentUser,
    db: SessionDep,
    page: PageParams = Depends(pagination_params),
    _sa=require_role(ROLE_SUPERADMIN),
):
    base = select(Tenant)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    tenants = (
        db.execute(
            base.order_by(Tenant.created_at.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        .scalars()
        .all()
    )
    items = [_to_list_item(t, db) for t in tenants]
    return PaginatedResponse[TenantListItem](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


# --------------------------------------------------------------------
# Create
# --------------------------------------------------------------------


@router.post(
    "",
    response_model=TenantListItem,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    data: TenantCreateRequest,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    slug = _slugify(data.tenant_name)
    if slug == TECNOMEDIA_TENANT_SLUG:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El slug 'tecnomedia' está reservado",
        )

    if (
        db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un tenant con ese nombre",
        )

    if (
        db.execute(
            select(User).where(User.email == str(data.admin_email))
        ).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un usuario con ese email",
        )

    tenant = Tenant(
        name=data.tenant_name,
        slug=slug,
        plan=data.plan,
        active=True,
    )
    db.add(tenant)
    db.flush()

    admin = User(
        tenant_id=tenant.id,
        email=str(data.admin_email),
        hashed_password=hash_password(data.admin_password),
        display_name=data.admin_display_name,
        role=ROLE_COMPANY_ADMIN,
        active=True,
    )
    db.add(admin)
    db.flush()

    audit(
        db,
        actor=user,
        action="tenant.created",
        target_type="tenant",
        target_id=tenant.id,
        payload={
            "name": data.tenant_name,
            "slug": slug,
            "plan": data.plan,
            "admin_email": str(data.admin_email),
            "admin_user_id": admin.id,
        },
    )
    db.commit()
    db.refresh(tenant)
    return _to_list_item(tenant, db)


# --------------------------------------------------------------------
# Get
# --------------------------------------------------------------------


@router.get("/{tenant_id}", response_model=TenantDetail)
def get_tenant(
    tenant_id: int,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    tenant = _get_tenant_or_404(tenant_id, db)
    users = (
        db.execute(
            select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
        )
        .scalars()
        .all()
    )
    list_item = _to_list_item(tenant, db)
    return TenantDetail(
        **list_item.model_dump(),
        users=[TenantUserItem.model_validate(u) for u in users],
    )


# --------------------------------------------------------------------
# Update
# --------------------------------------------------------------------


@router.patch("/{tenant_id}", response_model=TenantListItem)
def update_tenant(
    tenant_id: int,
    data: TenantUpdateRequest,
    user: CurrentUser,
    db: SessionDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    tenant = _get_tenant_or_404(tenant_id, db)

    changes: dict[str, dict[str, object]] = {}

    if data.name is not None and data.name != tenant.name:
        changes["name"] = {"from": tenant.name, "to": data.name}
        tenant.name = data.name

    if data.plan is not None and data.plan != tenant.plan:
        changes["plan"] = {"from": tenant.plan, "to": data.plan}
        tenant.plan = data.plan

    if data.active is not None and data.active != tenant.active:
        if tenant.slug == TECNOMEDIA_TENANT_SLUG and not data.active:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "No se puede suspender el tenant TecnoMedia",
            )
        changes["active"] = {"from": tenant.active, "to": data.active}
        tenant.active = data.active

    if changes:
        audit(
            db,
            actor=user,
            action="tenant.updated",
            target_type="tenant",
            target_id=tenant.id,
            payload={"changes": changes},
        )

    db.commit()
    db.refresh(tenant)
    return _to_list_item(tenant, db)


# --------------------------------------------------------------------
# Delete (hard, cascade)
# --------------------------------------------------------------------


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
    _sa=require_role(ROLE_SUPERADMIN),
):
    tenant = _get_tenant_or_404(tenant_id, db)
    if tenant.slug == TECNOMEDIA_TENANT_SLUG:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede eliminar el tenant TecnoMedia",
        )

    has_active = db.execute(
        select(Batch.id)
        .where(
            Batch.tenant_id == tenant_id,
            Batch.state.in_(_BATCH_ACTIVE_STATES),
        )
        .limit(1)
    ).first()
    if has_active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede eliminar el tenant porque tiene lotes en ejecución",
        )

    stats = _stats_for_tenant(db, tenant_id)
    snapshot = {
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "n_users": stats.n_users,
        "n_applications": stats.n_applications,
        "n_batches": stats.n_batches,
    }

    page_paths = (
        db.execute(
            select(Page.image_path)
            .join(Batch, Page.batch_id == Batch.id)
            .where(Batch.tenant_id == tenant_id, Page.image_path != "")
        )
        .scalars()
        .all()
    )
    for path in page_paths:
        try:
            storage.delete(path)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "No se pudo borrar %s al eliminar tenant %s: %s",
                path,
                tenant_id,
                exc,
            )

    apps = (
        db.execute(select(Application).where(Application.tenant_id == tenant_id))
        .scalars()
        .all()
    )
    for app in apps:
        db.delete(app)

    db.execute(Invitation.__table__.delete().where(Invitation.tenant_id == tenant_id))

    audit(
        db,
        actor=user,
        action="tenant.deleted",
        target_type="tenant",
        target_id=tenant_id,
        payload=snapshot,
    )

    db.delete(tenant)
    db.commit()
