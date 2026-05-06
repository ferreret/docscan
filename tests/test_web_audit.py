"""Tests del modelo AuditLog y del helper audit() (Hito 4)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
import web.api._register_models  # noqa: F401  registra todas las tablas

from web.api.audit import audit
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_SUPERADMIN,
    AuditLog,
    Tenant,
    User,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def superadmin(db_session):
    tenant = Tenant(name="TecnoMedia", slug="tecnomedia", plan="enterprise")
    db_session.add(tenant)
    db_session.flush()
    u = User(
        tenant_id=tenant.id,
        email="admin@tecnomedia.es",
        hashed_password="dummy",
        display_name="Admin",
        role=ROLE_SUPERADMIN,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def company_admin(db_session):
    tenant = Tenant(name="ACME", slug="acme", plan="free")
    db_session.add(tenant)
    db_session.flush()
    u = User(
        tenant_id=tenant.id,
        email="admin@acme.com",
        hashed_password="dummy",
        display_name="Admin ACME",
        role=ROLE_COMPANY_ADMIN,
    )
    db_session.add(u)
    db_session.commit()
    return u


class TestAuditHelper:
    def test_inserta_registro_basico(self, db_session, superadmin):
        audit(
            db_session,
            actor=superadmin,
            action="tenant.created",
            target_type="tenant",
            target_id=42,
            payload={"name": "ACME"},
        )
        db_session.commit()
        rows = db_session.execute(select(AuditLog)).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.actor_user_id == superadmin.id
        assert row.tenant_id == superadmin.tenant_id
        assert row.action == "tenant.created"
        assert row.target_type == "tenant"
        assert row.target_id == 42
        assert row.created_at is not None

    def test_payload_se_serializa_a_json(self, db_session, superadmin):
        audit(
            db_session,
            actor=superadmin,
            action="user.created",
            target_type="user",
            target_id=1,
            payload={"email": "x@y.com", "role": "operator"},
        )
        db_session.commit()
        row = db_session.execute(select(AuditLog)).scalar_one()
        assert json.loads(row.payload_json) == {
            "email": "x@y.com",
            "role": "operator",
        }

    def test_payload_default_es_dict_vacio(self, db_session, superadmin):
        audit(
            db_session,
            actor=superadmin,
            action="ping",
            target_type="system",
            target_id=None,
        )
        db_session.commit()
        row = db_session.execute(select(AuditLog)).scalar_one()
        assert json.loads(row.payload_json) == {}

    def test_target_id_puede_ser_null(self, db_session, superadmin):
        audit(
            db_session,
            actor=superadmin,
            action="login.failed",
            target_type="user",
            target_id=None,
            payload={"email": "noexiste@x.com"},
        )
        db_session.commit()
        row = db_session.execute(select(AuditLog)).scalar_one()
        assert row.target_id is None

    def test_actor_null_para_acciones_de_sistema(self, db_session):
        audit(
            db_session,
            actor=None,
            action="cron.recovery",
            target_type="batch",
            target_id=5,
        )
        db_session.commit()
        row = db_session.execute(select(AuditLog)).scalar_one()
        assert row.actor_user_id is None
        assert row.tenant_id is None

    def test_helper_no_hace_commit(self, db_session, superadmin):
        """``audit()`` solo añade y flush; el caller decide cuándo commit.

        Si el caller hace rollback, la entrada de audit también desaparece.
        """
        audit(
            db_session,
            actor=superadmin,
            action="tenant.suspended",
            target_type="tenant",
            target_id=10,
        )
        db_session.rollback()
        rows = db_session.execute(select(AuditLog)).scalars().all()
        assert rows == []

    def test_query_por_actor(self, db_session, superadmin, company_admin):
        audit(
            db_session,
            actor=superadmin,
            action="a",
            target_type="t",
            target_id=1,
        )
        audit(
            db_session,
            actor=superadmin,
            action="b",
            target_type="t",
            target_id=2,
        )
        audit(
            db_session,
            actor=company_admin,
            action="c",
            target_type="t",
            target_id=3,
        )
        audit(
            db_session,
            actor=None,
            action="d",
            target_type="t",
            target_id=4,
        )
        db_session.commit()
        rows = (
            db_session.execute(
                select(AuditLog).where(AuditLog.actor_user_id == superadmin.id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        actions = {r.action for r in rows}
        assert actions == {"a", "b"}

    def test_query_por_tenant(self, db_session, superadmin, company_admin):
        audit(
            db_session,
            actor=superadmin,
            action="x",
            target_type="t",
            target_id=1,
        )
        audit(
            db_session,
            actor=company_admin,
            action="y",
            target_type="t",
            target_id=2,
        )
        db_session.commit()
        rows = (
            db_session.execute(
                select(AuditLog).where(AuditLog.tenant_id == company_admin.tenant_id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].action == "y"


class TestAuditLogModel:
    def test_columnas_requeridas(self, db_session, superadmin):
        """action y target_type son NOT NULL."""
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db_session.add(
                AuditLog(
                    actor_user_id=superadmin.id,
                    tenant_id=superadmin.tenant_id,
                    action=None,
                    target_type="tenant",
                    target_id=1,
                    payload_json="{}",
                )
            )
            db_session.flush()
