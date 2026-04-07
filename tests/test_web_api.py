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
    def test_me_autenticado(self, client):
        h = _auth_header(client, "admin@corp.com", "secret", "Admin Corp", "MyCorp")
        resp = client.get("/api/auth/me", headers=h)
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


# ------------------------------------------------------------------
# CRUD de aplicaciones
# ------------------------------------------------------------------


def _auth_header(
    client,
    email: str = "dev@acme.com",
    password: str = "pass",
    display_name: str = "Dev",
    tenant_name: str = "ACME",
) -> dict:
    """Registra usuario y devuelve headers con JWT."""
    client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "display_name": display_name,
        "tenant_name": tenant_name,
    })
    resp = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestApplicationsCRUD:
    def test_lista_vacia(self, client):
        h = _auth_header(client)
        resp = client.get("/api/applications", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_crear_aplicacion(self, client):
        h = _auth_header(client)
        resp = client.post("/api/applications", headers=h, json={
            "name": "Facturas",
            "description": "Proceso de facturas",
            "output_format": "pdf",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Facturas"
        assert data["output_format"] == "pdf"
        assert data["tenant_id"] is not None
        assert data["pipeline_json"] == "[]"

    def test_listar_tras_crear(self, client):
        h = _auth_header(client)
        client.post("/api/applications", headers=h, json={"name": "App1"})
        client.post("/api/applications", headers=h, json={"name": "App2"})
        resp = client.get("/api/applications", headers=h)
        assert len(resp.json()) == 2

    def test_obtener_por_id(self, client):
        h = _auth_header(client)
        created = client.post("/api/applications", headers=h, json={
            "name": "MiApp",
        }).json()
        resp = client.get(f"/api/applications/{created['id']}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["name"] == "MiApp"

    def test_actualizar(self, client):
        h = _auth_header(client)
        created = client.post("/api/applications", headers=h, json={
            "name": "Original",
        }).json()
        resp = client.patch(
            f"/api/applications/{created['id']}",
            headers=h,
            json={"name": "Renombrada", "description": "Nueva desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renombrada"
        assert resp.json()["description"] == "Nueva desc"

    def test_eliminar(self, client):
        h = _auth_header(client)
        created = client.post("/api/applications", headers=h, json={
            "name": "Borrame",
        }).json()
        resp = client.delete(f"/api/applications/{created['id']}", headers=h)
        assert resp.status_code == 204
        resp = client.get(f"/api/applications/{created['id']}", headers=h)
        assert resp.status_code == 404

    def test_nombre_duplicado(self, client):
        h = _auth_header(client)
        client.post("/api/applications", headers=h, json={"name": "Unica"})
        resp = client.post("/api/applications", headers=h, json={"name": "Unica"})
        assert resp.status_code == 409

    def test_no_ve_apps_otro_tenant(self, client):
        h1 = _auth_header(client)
        created = client.post("/api/applications", headers=h1, json={
            "name": "SecretApp",
        }).json()

        # Registrar segundo tenant
        client.post("/api/auth/register", json={
            "email": "otro@otro.com",
            "password": "pass",
            "display_name": "Otro",
            "tenant_name": "OtraCorp",
        })
        resp2 = client.post("/api/auth/login", json={
            "email": "otro@otro.com",
            "password": "pass",
        })
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Tenant 2 no ve las apps de tenant 1
        resp = client.get("/api/applications", headers=h2)
        assert resp.json() == []

        resp = client.get(f"/api/applications/{created['id']}", headers=h2)
        assert resp.status_code == 404

    def test_sin_autenticacion(self, client):
        resp = client.get("/api/applications")
        assert resp.status_code == 401
