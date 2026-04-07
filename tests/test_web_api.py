"""Tests de integración para la API web de DocScan Studio.

Usa SQLite en memoria para los tests (no requiere PostgreSQL).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base

# Importar modelos para registrar las tablas
from app.models.application import Application  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from web.api.models import Tenant, User  # noqa: F401

import web.api.database as _db_module
from web.api.database import get_db
from web.api.main import create_app


@pytest.fixture
def _test_engine():
    """Engine SQLite en memoria compartible entre hilos."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    # Inyectar engine de test en el singleton para que el lifespan lo use
    _db_module._engine = engine
    yield engine
    _db_module._engine = None
    _db_module._SessionFactory = None
    engine.dispose()


@pytest.fixture
def db_session(_test_engine):
    """Sesión para tests directos de modelos."""
    factory = sessionmaker(bind=_test_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_test_engine):
    """TestClient con dependencia de BD sobreescrita."""
    factory = sessionmaker(bind=_test_engine)
    app = create_app()

    def _override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ------------------------------------------------------------------
# Registro
# ------------------------------------------------------------------


class TestRegister:
    def test_registro_exitoso(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "admin@acme.com",
            "password": "secreto123",
            "display_name": "Admin ACME",
            "tenant_name": "ACME Corp",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "admin@acme.com"
        assert data["role"] == "company_admin"
        assert data["tenant_name"] == "ACME Corp"
        assert data["tenant_id"] > 0

    def test_registro_email_duplicado(self, client):
        payload = {
            "email": "admin@acme.com",
            "password": "secreto123",
            "display_name": "Admin",
            "tenant_name": "ACME",
        }
        client.post("/api/auth/register", json=payload)
        resp = client.post("/api/auth/register", json={
            **payload,
            "tenant_name": "Otro",
        })
        assert resp.status_code == 409

    def test_registro_tenant_duplicado(self, client):
        payload = {
            "email": "admin@acme.com",
            "password": "secreto123",
            "display_name": "Admin",
            "tenant_name": "ACME",
        }
        client.post("/api/auth/register", json=payload)
        resp = client.post("/api/auth/register", json={
            "email": "otro@otro.com",
            "password": "secreto123",
            "display_name": "Otro",
            "tenant_name": "ACME",
        })
        assert resp.status_code == 409


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------


class TestLogin:
    def _register(self, client):
        client.post("/api/auth/register", json={
            "email": "user@test.com",
            "password": "pass123",
            "display_name": "Test User",
            "tenant_name": "TestCo",
        })

    def test_login_exitoso(self, client):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_password_incorrecta(self, client):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_email_no_existe(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "noexiste@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Perfil autenticado
# ------------------------------------------------------------------


class TestProfile:
    def _get_token(self, client) -> str:
        client.post("/api/auth/register", json={
            "email": "admin@corp.com",
            "password": "secret",
            "display_name": "Admin Corp",
            "tenant_name": "MyCorp",
        })
        resp = client.post("/api/auth/login", json={
            "email": "admin@corp.com",
            "password": "secret",
        })
        return resp.json()["access_token"]

    def test_me_autenticado(self, client):
        token = self._get_token(client)
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@corp.com"
        assert data["role"] == "company_admin"
        assert data["tenant_name"] == "MyCorp"

    def test_me_sin_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_token_invalido(self, client):
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer tokeninvalido"},
        )
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Modelos existentes con tenant_id
# ------------------------------------------------------------------


class TestTenantId:
    def test_application_acepta_tenant_id_null(self, db_session):
        """El desktop crea aplicaciones sin tenant_id (None)."""
        from app.models.application import Application
        app = Application(name="TestApp", tenant_id=None)
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)
        assert app.tenant_id is None
        assert app.id > 0

    def test_application_acepta_tenant_id(self, db_session):
        """La web crea aplicaciones con tenant_id."""
        from app.models.application import Application
        tenant = Tenant(name="TestTenant", slug="test-tenant")
        db_session.add(tenant)
        db_session.flush()
        app = Application(name="WebApp", tenant_id=tenant.id)
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)
        assert app.tenant_id == tenant.id

    def test_batch_acepta_tenant_id_null(self, db_session):
        """El desktop crea lotes sin tenant_id."""
        from app.models.application import Application
        from app.models.batch import Batch
        app = Application(name="App1")
        db_session.add(app)
        db_session.flush()
        batch = Batch(application_id=app.id, tenant_id=None)
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)
        assert batch.tenant_id is None
