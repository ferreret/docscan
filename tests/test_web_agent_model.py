"""Tests del modelo ORM ``AgentDevice`` (Hito 2 sprint cliente local).

Cubre persistencia básica, defaults, foreign keys cascade desde User y
Tenant, y unicidad del ``pairing_code``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
import web.api._register_models  # noqa: F401  registra todas las tablas

from web.api.models import AgentDevice, ROLE_OPERATOR, Tenant, User


# --------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------


@pytest.fixture
def _test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(_test_engine):
    factory = sessionmaker(bind=_test_engine)
    with factory() as s:
        yield s


@pytest.fixture
def tenant_and_user(session):
    """Crea un tenant + user mínimos para los tests."""
    tenant = Tenant(name="Acme", slug="acme")
    session.add(tenant)
    session.flush()

    user = User(
        tenant_id=tenant.id,
        email="ana@acme.test",
        hashed_password="hash",
        display_name="Ana",
        role=ROLE_OPERATOR,
    )
    session.add(user)
    session.commit()
    return tenant, user


# --------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------


class TestAgentDeviceBasics:
    def test_insertar_y_leer_minimal(self, session, tenant_and_user):
        tenant, user = tenant_and_user
        device = AgentDevice(
            user_id=user.id,
            tenant_id=tenant.id,
            name="Portátil Ana",
        )
        session.add(device)
        session.commit()

        loaded = session.execute(
            select(AgentDevice).where(AgentDevice.id == device.id)
        ).scalar_one()
        assert loaded.name == "Portátil Ana"
        assert loaded.user_id == user.id
        assert loaded.tenant_id == tenant.id
        assert loaded.active is True
        assert loaded.created_at is not None

    def test_defaults_pre_pairing(self, session, tenant_and_user):
        tenant, user = tenant_and_user
        device = AgentDevice(user_id=user.id, tenant_id=tenant.id, name="d1")
        session.add(device)
        session.commit()

        # Pre-pairing: token y paired_at son NULL.
        assert device.token_hash is None
        assert device.paired_at is None
        assert device.last_seen is None
        # pairing_code también NULL hasta que pair-init lo establezca.
        assert device.pairing_code is None
        assert device.code_expires_at is None

    def test_pairing_completo(self, session, tenant_and_user):
        """Simula el flujo completo: pair-init → claim."""
        tenant, user = tenant_and_user

        # 1. pair-init: backend crea AgentDevice con código.
        device = AgentDevice(
            user_id=user.id,
            tenant_id=tenant.id,
            name="Estación de Ana",
            pairing_code="ABCD1234",
            code_expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(device)
        session.commit()
        assert device.pairing_code == "ABCD1234"
        assert device.token_hash is None

        # 2. pair-claim: backend genera token, nullea código.
        device.pairing_code = None
        device.code_expires_at = None
        device.token_hash = "$2b$12$hash..."
        device.paired_at = datetime.utcnow()
        session.commit()

        session.refresh(device)
        assert device.pairing_code is None
        assert device.token_hash is not None
        assert device.paired_at is not None


class TestAgentDeviceConstraints:
    def test_pairing_code_unico(self, session, tenant_and_user):
        tenant, user = tenant_and_user
        d1 = AgentDevice(
            user_id=user.id,
            tenant_id=tenant.id,
            name="d1",
            pairing_code="DUPCODE1",
        )
        session.add(d1)
        session.commit()

        d2 = AgentDevice(
            user_id=user.id,
            tenant_id=tenant.id,
            name="d2",
            pairing_code="DUPCODE1",
        )
        session.add(d2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_id_es_obligatorio(self, session, tenant_and_user):
        tenant, _ = tenant_and_user
        device = AgentDevice(tenant_id=tenant.id, name="huerfano")
        session.add(device)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_tenant_id_es_obligatorio(self, session, tenant_and_user):
        _, user = tenant_and_user
        device = AgentDevice(user_id=user.id, name="huerfano")
        session.add(device)
        with pytest.raises(IntegrityError):
            session.commit()


class TestAgentDeviceFKs:
    def test_user_id_inexistente_falla(self, session, tenant_and_user):
        tenant, _ = tenant_and_user
        device = AgentDevice(user_id=99999, tenant_id=tenant.id, name="d")
        session.add(device)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_tenant_id_inexistente_falla(self, session, tenant_and_user):
        _, user = tenant_and_user
        device = AgentDevice(user_id=user.id, tenant_id=99999, name="d")
        session.add(device)
        with pytest.raises(IntegrityError):
            session.commit()


class TestAgentDeviceRepr:
    def test_repr_no_paired(self, session, tenant_and_user):
        tenant, user = tenant_and_user
        device = AgentDevice(user_id=user.id, tenant_id=tenant.id, name="d-test")
        session.add(device)
        session.commit()
        assert "paired=False" in repr(device)
        assert "d-test" in repr(device)

    def test_repr_paired(self, session, tenant_and_user):
        tenant, user = tenant_and_user
        device = AgentDevice(
            user_id=user.id,
            tenant_id=tenant.id,
            name="d",
            paired_at=datetime.utcnow(),
        )
        session.add(device)
        session.commit()
        assert "paired=True" in repr(device)
