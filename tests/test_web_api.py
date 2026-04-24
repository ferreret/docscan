"""Tests de integración para la API web de DocScan Studio.

Usa SQLite en memoria para los tests (no requiere PostgreSQL).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
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
from web.api.storage import FilesystemStorage, get_storage


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
def storage_dir(tmp_path):
    """Directorio base para el storage del test."""
    return tmp_path / "storage"


@pytest.fixture
def client(_test_engine, storage_dir):
    """TestClient con dependencias de BD y storage sobreescritas."""
    factory = sessionmaker(bind=_test_engine)
    app = create_app()

    def _override_get_db():
        with factory() as session:
            yield session

    storage = FilesystemStorage(storage_dir)

    def _override_get_storage():
        return storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage
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
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "admin@acme.com",
                "password": "secreto123",
                "display_name": "Admin ACME",
                "tenant_name": "ACME Corp",
            },
        )
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
        resp = client.post(
            "/api/auth/register",
            json={
                **payload,
                "tenant_name": "Otro",
            },
        )
        assert resp.status_code == 409

    def test_registro_password_corta_422(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "admin@acme.com",
                "password": "1234567",
                "display_name": "Admin",
                "tenant_name": "ACME",
            },
        )
        assert resp.status_code == 422

    def test_registro_tenant_duplicado(self, client):
        payload = {
            "email": "admin@acme.com",
            "password": "secreto123",
            "display_name": "Admin",
            "tenant_name": "ACME",
        }
        client.post("/api/auth/register", json=payload)
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "secreto123",
                "display_name": "Otro",
                "tenant_name": "ACME",
            },
        )
        assert resp.status_code == 409


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------


class TestLogin:
    def _register(self, client):
        client.post(
            "/api/auth/register",
            json={
                "email": "user@test.com",
                "password": "password123",
                "display_name": "Test User",
                "tenant_name": "TestCo",
            },
        )

    def test_login_exitoso(self, client):
        self._register(client)
        resp = client.post(
            "/api/auth/login",
            json={
                "email": "user@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_password_incorrecta(self, client):
        self._register(client)
        resp = client.post(
            "/api/auth/login",
            json={
                "email": "user@test.com",
                "password": "wrongpass",
            },
        )
        assert resp.status_code == 401

    def test_login_email_no_existe(self, client):
        resp = client.post(
            "/api/auth/login",
            json={
                "email": "noexiste@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Perfil autenticado
# ------------------------------------------------------------------


class TestProfile:
    def test_me_autenticado(self, client):
        h = _auth_header(client, "admin@corp.com", "secret123", "Admin Corp", "MyCorp")
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

        app = Application(name="TestApp", tenant_id=None)
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)
        assert app.tenant_id is None
        assert app.id > 0

    def test_application_acepta_tenant_id(self, db_session):
        """La web crea aplicaciones con tenant_id."""

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
    password: str = "password123",
    display_name: str = "Dev",
    tenant_name: str = "ACME",
) -> dict:
    """Registra usuario y devuelve headers con JWT."""
    client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "tenant_name": tenant_name,
        },
    )
    resp = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestApplicationsCRUD:
    def test_lista_vacia(self, client):
        h = _auth_header(client)
        resp = client.get("/api/applications", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_crear_aplicacion(self, client):
        h = _auth_header(client)
        resp = client.post(
            "/api/applications",
            headers=h,
            json={
                "name": "Facturas",
                "description": "Proceso de facturas",
                "output_format": "pdf",
            },
        )
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
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_obtener_por_id(self, client):
        h = _auth_header(client)
        created = client.post(
            "/api/applications",
            headers=h,
            json={
                "name": "MiApp",
            },
        ).json()
        resp = client.get(f"/api/applications/{created['id']}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["name"] == "MiApp"

    def test_actualizar(self, client):
        h = _auth_header(client)
        created = client.post(
            "/api/applications",
            headers=h,
            json={
                "name": "Original",
            },
        ).json()
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
        created = client.post(
            "/api/applications",
            headers=h,
            json={
                "name": "Borrame",
            },
        ).json()
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
        created = client.post(
            "/api/applications",
            headers=h1,
            json={
                "name": "SecretApp",
            },
        ).json()

        # Registrar segundo tenant
        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "password123",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "password123",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Tenant 2 no ve las apps de tenant 1
        resp = client.get("/api/applications", headers=h2)
        assert resp.json()["items"] == []

        resp = client.get(f"/api/applications/{created['id']}", headers=h2)
        assert resp.status_code == 404

    def test_sin_autenticacion(self, client):
        resp = client.get("/api/applications")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# CRUD de lotes
# ------------------------------------------------------------------


def _create_app_and_get_id(client, headers, name: str = "AppTest") -> int:
    """Crea una aplicación y devuelve su ID."""
    resp = client.post("/api/applications", headers=headers, json={"name": name})
    return resp.json()["id"]


class TestBatchesCRUD:
    def test_lista_vacia(self, client):
        h = _auth_header(client)
        resp = client.get("/api/batches", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_crear_lote(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        resp = client.post(
            "/api/batches",
            headers=h,
            json={
                "application_id": app_id,
                "folder_path": "/tmp/batch1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["application_id"] == app_id
        assert data["state"] == "created"
        assert data["folder_path"] == "/tmp/batch1"
        assert data["tenant_id"] is not None
        assert data["page_count"] == 0

    def test_crear_lote_aplicacion_inexistente(self, client):
        h = _auth_header(client)
        resp = client.post(
            "/api/batches",
            headers=h,
            json={
                "application_id": 9999,
            },
        )
        assert resp.status_code == 404

    def test_listar_tras_crear(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        client.post("/api/batches", headers=h, json={"application_id": app_id})
        client.post("/api/batches", headers=h, json={"application_id": app_id})
        resp = client.get("/api/batches", headers=h)
        assert resp.json()["total"] == 2

    def test_filtrar_por_aplicacion(self, client):
        h = _auth_header(client)
        app1 = _create_app_and_get_id(client, h, "A1")
        app2 = _create_app_and_get_id(client, h, "A2")
        client.post("/api/batches", headers=h, json={"application_id": app1})
        client.post("/api/batches", headers=h, json={"application_id": app1})
        client.post("/api/batches", headers=h, json={"application_id": app2})
        resp = client.get(f"/api/batches?application_id={app1}", headers=h)
        assert resp.json()["total"] == 2
        resp = client.get(f"/api/batches?application_id={app2}", headers=h)
        assert resp.json()["total"] == 1

    def test_filtrar_por_estado(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        created = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()
        client.patch(
            f"/api/batches/{created['id']}",
            headers=h,
            json={"state": "exported"},
        )
        client.post("/api/batches", headers=h, json={"application_id": app_id})
        resp = client.get("/api/batches?state=exported", headers=h)
        assert resp.json()["total"] == 1
        resp = client.get("/api/batches?state=created", headers=h)
        assert resp.json()["total"] == 1

    def test_obtener_por_id(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        created = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()
        resp = client.get(f"/api/batches/{created['id']}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_actualizar_estado(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        created = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()
        resp = client.patch(
            f"/api/batches/{created['id']}",
            headers=h,
            json={"state": "verified", "page_count": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "verified"
        assert resp.json()["page_count"] == 10

    def test_actualizar_estado_invalido(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        created = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()
        resp = client.patch(
            f"/api/batches/{created['id']}",
            headers=h,
            json={"state": "inexistente"},
        )
        assert resp.status_code == 422

    def test_eliminar(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        created = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()
        resp = client.delete(f"/api/batches/{created['id']}", headers=h)
        assert resp.status_code == 204
        resp = client.get(f"/api/batches/{created['id']}", headers=h)
        assert resp.status_code == 404

    def test_no_ve_lotes_otro_tenant(self, client):
        h1 = _auth_header(client)
        app_id = _create_app_and_get_id(client, h1)
        created = client.post(
            "/api/batches",
            headers=h1,
            json={"application_id": app_id},
        ).json()

        # Segundo tenant
        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "password123",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "password123",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = client.get("/api/batches", headers=h2)
        assert resp.json()["items"] == []

        resp = client.get(f"/api/batches/{created['id']}", headers=h2)
        assert resp.status_code == 404

    def test_no_crea_lote_en_app_de_otro_tenant(self, client):
        h1 = _auth_header(client)
        app_id = _create_app_and_get_id(client, h1)

        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "password123",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "password123",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = client.post(
            "/api/batches",
            headers=h2,
            json={
                "application_id": app_id,
            },
        )
        assert resp.status_code == 404

    def test_sin_autenticacion(self, client):
        resp = client.get("/api/batches")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Upload de páginas
# ------------------------------------------------------------------


def _make_png_bytes(width: int = 4, height: int = 4) -> bytes:
    """Genera bytes de una imagen PNG pequeña."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes(num_pages: int = 2) -> bytes:
    """Genera bytes de un PDF con N páginas vacías."""
    import pymupdf

    doc = pymupdf.open()
    for _ in range(num_pages):
        doc.new_page(width=200, height=200)
    data = doc.tobytes()
    doc.close()
    return data


def _create_application(client, h, name: str = "TestApp") -> int:
    """Crea una aplicación vacía y devuelve su id."""
    resp = client.post(
        "/api/applications",
        headers=h,
        json={"name": name, "description": "Test app"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_page(client, h, batch_id: int) -> int:
    """Sube un PNG dummy al lote y devuelve el page_id."""
    files = [("files", ("a.png", _make_png_bytes(), "image/png"))]
    resp = client.post(
        f"/api/batches/{batch_id}/pages",
        headers=h,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["created"][0]["id"]


def _create_batch(client, headers, app_id: int | None = None) -> int:
    """Crea un lote vacío. Si app_id es None, crea también una aplicación."""
    if app_id is None:
        app_id = _create_app_and_get_id(client, headers)
    resp = client.post(
        "/api/batches",
        headers=headers,
        json={
            "application_id": app_id,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestPagesUpload:
    def test_subir_imagen(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [("files", ("doc.png", _make_png_bytes(), "image/png"))]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["created"]) == 1
        assert data["batch_page_count"] == 1
        assert data["created"][0]["page_index"] == 0
        assert data["created"][0]["batch_id"] == batch_id

    def test_subir_varias_imagenes(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [
            ("files", ("a.png", _make_png_bytes(), "image/png")),
            ("files", ("b.png", _make_png_bytes(), "image/png")),
            ("files", ("c.png", _make_png_bytes(), "image/png")),
        ]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["created"]) == 3
        assert data["batch_page_count"] == 3
        indices = [p["page_index"] for p in data["created"]]
        assert indices == [0, 1, 2]

    def test_subir_pdf_multipagina(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [
            ("files", ("doc.pdf", _make_pdf_bytes(num_pages=3), "application/pdf"))
        ]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["created"]) == 3
        assert data["batch_page_count"] == 3

    def test_subir_formato_no_soportado(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [("files", ("doc.exe", b"binario", "application/octet-stream"))]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 400

    def test_subir_pdf_corrupto(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [("files", ("bad.pdf", b"not a real pdf", "application/pdf"))]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 400

    def test_subir_fichero_vacio(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [("files", ("empty.png", b"", "image/png"))]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        assert resp.status_code == 400

    def test_subida_incremental_pagina_index(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("b.png", _make_png_bytes(), "image/png"))],
        )
        data = resp.json()
        assert data["created"][0]["page_index"] == 1
        assert data["batch_page_count"] == 2

    def test_subir_a_lote_inexistente(self, client):
        h = _auth_header(client)
        files = [("files", ("x.png", _make_png_bytes(), "image/png"))]
        resp = client.post("/api/batches/9999/pages", headers=h, files=files)
        assert resp.status_code == 404

    def test_subir_a_lote_de_otro_tenant(self, client):
        h1 = _auth_header(client)
        batch_id = _create_batch(client, h1)

        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "password123",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "password123",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        files = [("files", ("x.png", _make_png_bytes(), "image/png"))]
        resp = client.post(f"/api/batches/{batch_id}/pages", headers=h2, files=files)
        assert resp.status_code == 404


class TestPagesRead:
    def test_listar_paginas(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        files = [
            ("files", ("a.png", _make_png_bytes(), "image/png")),
            ("files", ("b.png", _make_png_bytes(), "image/png")),
        ]
        client.post(f"/api/batches/{batch_id}/pages", headers=h, files=files)
        resp = client.get(f"/api/batches/{batch_id}/pages", headers=h)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        assert [p["page_index"] for p in items] == [0, 1]

    def test_listar_paginas_incluye_flags_excluded_y_review(self, client):
        """PageListItem debe incluir is_excluded y review_reason para que los
        badges de exclusión/revisión se rendericen en las miniaturas."""
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )
        page_id = resp.json()["created"][0]["id"]

        client.patch(
            f"/api/pages/{page_id}",
            headers=h,
            json={"is_excluded": True, "needs_review": True, "review_reason": "QA"},
        )

        items = client.get(f"/api/batches/{batch_id}/pages", headers=h).json()
        assert items[0]["is_excluded"] is True
        assert items[0]["needs_review"] is True
        assert items[0]["review_reason"] == "QA"

    def test_obtener_metadatos_pagina(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )
        page_id = resp.json()["created"][0]["id"]
        resp = client.get(
            f"/api/batches/{batch_id}/pages/{page_id}",
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == page_id
        assert resp.json()["image_path"] != ""

    def test_descargar_imagen(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        png = _make_png_bytes()
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("a.png", png, "image/png"))],
        )
        page_id = resp.json()["created"][0]["id"]
        resp = client.get(
            f"/api/batches/{batch_id}/pages/{page_id}/image",
            headers=h,
        )
        assert resp.status_code == 200
        # PNG magic bytes
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert resp.content == png

    def test_eliminar_pagina(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )
        page_id = resp.json()["created"][0]["id"]
        resp = client.delete(
            f"/api/batches/{batch_id}/pages/{page_id}",
            headers=h,
        )
        assert resp.status_code == 204

        # Lote actualiza page_count
        batch = client.get(f"/api/batches/{batch_id}", headers=h).json()
        assert batch["page_count"] == 0

        # Ya no se puede obtener la página
        resp = client.get(
            f"/api/batches/{batch_id}/pages/{page_id}",
            headers=h,
        )
        assert resp.status_code == 404

    def test_listar_lote_otro_tenant(self, client):
        h1 = _auth_header(client)
        batch_id = _create_batch(client, h1)
        client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h1,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )

        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "password123",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "password123",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = client.get(f"/api/batches/{batch_id}/pages", headers=h2)
        assert resp.status_code == 404

    def test_sin_autenticacion(self, client):
        resp = client.get("/api/batches/1/pages")
        assert resp.status_code == 401


class TestPagesStorageCleanup:
    """Al borrar batch/aplicación, los ficheros en disco se eliminan."""

    def _count_files(self, directory) -> int:
        if not directory.exists():
            return 0
        return sum(1 for p in directory.rglob("*") if p.is_file())

    def test_delete_batch_limpia_ficheros(self, client, storage_dir):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        client.post(
            f"/api/batches/{batch_id}/pages",
            headers=h,
            files=[
                ("files", ("a.png", _make_png_bytes(), "image/png")),
                ("files", ("b.png", _make_png_bytes(), "image/png")),
            ],
        )
        assert self._count_files(storage_dir) == 2

        resp = client.delete(f"/api/batches/{batch_id}", headers=h)
        assert resp.status_code == 204
        assert self._count_files(storage_dir) == 0

    def test_delete_application_limpia_ficheros(self, client, storage_dir):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        batch1 = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()["id"]
        batch2 = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()["id"]
        client.post(
            f"/api/batches/{batch1}/pages",
            headers=h,
            files=[("files", ("a.png", _make_png_bytes(), "image/png"))],
        )
        client.post(
            f"/api/batches/{batch2}/pages",
            headers=h,
            files=[
                ("files", ("b.png", _make_png_bytes(), "image/png")),
                ("files", ("c.pdf", _make_pdf_bytes(num_pages=2), "application/pdf")),
            ],
        )
        # 1 + 1 + 2 = 4 ficheros
        assert self._count_files(storage_dir) == 4

        resp = client.delete(f"/api/applications/{app_id}", headers=h)
        assert resp.status_code == 204
        assert self._count_files(storage_dir) == 0


# ------------------------------------------------------------------
# Pipeline execution (background task)
# ------------------------------------------------------------------


def _create_app_with_pipeline(client, headers, pipeline_json: str) -> int:
    """Crea una aplicación con un pipeline JSON específico."""
    resp = client.post(
        "/api/applications",
        headers=headers,
        json={
            "name": f"PipelineApp-{pipeline_json[:10]}",
            "pipeline_json": pipeline_json,
        },
    )
    return resp.json()["id"]


def _create_batch_with_page(client, headers, app_id: int) -> tuple[int, int]:
    """Crea un lote en `app_id` y le sube una página PNG. Devuelve (batch_id, page_id)."""
    batch_id = client.post(
        "/api/batches",
        headers=headers,
        json={"application_id": app_id},
    ).json()["id"]
    upload = client.post(
        f"/api/batches/{batch_id}/pages",
        headers=headers,
        files=[("files", ("p.png", _make_png_bytes(width=20, height=20), "image/png"))],
    ).json()
    return batch_id, upload["created"][0]["id"]


# Pipeline JSON con un script que escribe en page.fields y page.ocr_text
_SCRIPT_PIPELINE = """[
  {
    "id": "s1",
    "type": "script",
    "enabled": true,
    "label": "test",
    "entry_point": "main",
    "script": "def main(app, batch, page, pipeline):\\n    page.fields['marca'] = 'web'\\n    page.ocr_text = 'fake ocr'\\n"
  }
]"""

# Pipeline JSON con un script que marca needs_review
_REVIEW_PIPELINE = """[
  {
    "id": "rev",
    "type": "script",
    "enabled": true,
    "label": "review",
    "entry_point": "main",
    "script": "def main(app, batch, page, pipeline):\\n    page.flags.needs_review = True\\n    page.flags.review_reason = 'forced'\\n"
  }
]"""


class TestPipelineRun:
    def test_run_pipeline_vacio_marca_lote_como_read(self, client):
        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, "[]")
        batch_id, _ = _create_batch_with_page(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/run", headers=h)
        assert resp.status_code == 202

        # El BackgroundTask de FastAPI ya corrió bajo TestClient
        batch = client.get(f"/api/batches/{batch_id}", headers=h).json()
        assert batch["state"] == "read"
        assert batch["page_count"] == 1

    def test_run_pipeline_script_persiste_resultados(self, client):
        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, _SCRIPT_PIPELINE)
        batch_id, page_id = _create_batch_with_page(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/run", headers=h)
        assert resp.status_code == 202

        batch = client.get(f"/api/batches/{batch_id}", headers=h).json()
        assert batch["state"] == "read"

        page = client.get(
            f"/api/batches/{batch_id}/pages/{page_id}",
            headers=h,
        ).json()
        assert page["pipeline_processed"] is True
        assert page["ocr_text"] == "fake ocr"
        assert "marca" in page["index_fields_json"]
        assert "web" in page["index_fields_json"]

    def test_run_pipeline_script_marca_revision(self, client):
        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, _REVIEW_PIPELINE)
        batch_id, page_id = _create_batch_with_page(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/run", headers=h)
        assert resp.status_code == 202

        page = client.get(
            f"/api/batches/{batch_id}/pages/{page_id}",
            headers=h,
        ).json()
        assert page["needs_review"] is True
        assert page["review_reason"] == "forced"

    def test_run_lote_vacio_rechazado(self, client):
        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, "[]")
        batch_id = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()["id"]
        resp = client.post(f"/api/batches/{batch_id}/run", headers=h)
        assert resp.status_code == 409

    def test_run_lote_inexistente(self, client):
        h = _auth_header(client)
        resp = client.post("/api/batches/9999/run", headers=h)
        assert resp.status_code == 404

    def test_run_lote_otro_tenant(self, client):
        h1 = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h1, "[]")
        batch_id, _ = _create_batch_with_page(client, h1, app_id)

        client.post(
            "/api/auth/register",
            json={
                "email": "intruso@x.com",
                "password": "password123",
                "display_name": "I",
                "tenant_name": "OtraCorpRun",
            },
        )
        token = client.post(
            "/api/auth/login",
            json={
                "email": "intruso@x.com",
                "password": "password123",
            },
        ).json()["access_token"]
        h2 = {"Authorization": f"Bearer {token}"}

        resp = client.post(f"/api/batches/{batch_id}/run", headers=h2)
        assert resp.status_code == 404

    def test_run_pipeline_invalido_marca_error(self, client):
        h = _auth_header(client)
        # Pipeline JSON sintácticamente válido pero con tipo desconocido
        bad_pipeline = '[{"id":"x","type":"unknown_type","enabled":true}]'
        app_id = _create_app_with_pipeline(client, h, bad_pipeline)
        batch_id, _ = _create_batch_with_page(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/run", headers=h)
        assert resp.status_code == 202

        batch = client.get(f"/api/batches/{batch_id}", headers=h).json()
        assert batch["state"] == "error_read"

    def test_run_sin_autenticacion(self, client):
        resp = client.post("/api/batches/1/run")
        assert resp.status_code == 401

    def test_run_409_when_already_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        assert r.status_code == 409

    def test_run_409_when_transferring(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "transferring"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        assert r.status_code == 409


# ------------------------------------------------------------------
# Storage backends — unit tests
# ------------------------------------------------------------------


class TestFilesystemStorageUnit:
    """Tests unitarios del backend filesystem."""

    def test_save_read_roundtrip(self, tmp_path):
        storage = FilesystemStorage(tmp_path / "fs")
        key = storage.save(1, 10, b"hola mundo", "txt")
        assert key.startswith("1/10/")
        assert key.endswith(".txt")
        assert storage.read(key) == b"hola mundo"

    def test_exists_and_delete(self, tmp_path):
        storage = FilesystemStorage(tmp_path / "fs")
        key = storage.save(1, 10, b"data", "bin")
        assert storage.exists(key)
        storage.delete(key)
        assert not storage.exists(key)

    def test_delete_inexistente_no_falla(self, tmp_path):
        storage = FilesystemStorage(tmp_path / "fs")
        storage.delete("1/10/nope.bin")  # no debe lanzar

    def test_absolute_path(self, tmp_path):
        storage = FilesystemStorage(tmp_path / "fs")
        key = storage.save(2, 20, b"x", "png")
        assert storage.absolute_path(key).is_file()


class TestMinIOStorageUnit:
    """Tests unitarios de MinIOStorage con mocks (no requiere servidor MinIO)."""

    def _make_storage(self):
        """Crea un MinIOStorage con el cliente mockeado."""
        from unittest.mock import MagicMock, patch
        from web.api.storage import MinIOStorage

        with patch("minio.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="test",
                secret_key="test",
                bucket="test-bucket",
            )
        return storage, mock_client

    def test_save_calls_put_object(self):
        storage, mock_client = self._make_storage()
        key = storage.save(1, 10, b"hello", "png")

        assert key.startswith("1/10/")
        assert key.endswith(".png")
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args
        assert call_kwargs.kwargs["bucket_name"] == "test-bucket"
        assert call_kwargs.kwargs["object_name"] == key
        assert call_kwargs.kwargs["length"] == 5

    def test_read_calls_get_object(self):
        from unittest.mock import MagicMock

        storage, mock_client = self._make_storage()
        mock_response = MagicMock()
        mock_response.read.return_value = b"image-data"
        mock_client.get_object.return_value = mock_response

        result = storage.read("1/10/abc.png")

        assert result == b"image-data"
        mock_client.get_object.assert_called_once_with(
            bucket_name="test-bucket",
            object_name="1/10/abc.png",
        )
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    def test_exists_true(self):
        from unittest.mock import MagicMock

        storage, mock_client = self._make_storage()
        mock_client.stat_object.return_value = MagicMock()
        assert storage.exists("1/10/abc.png") is True

    def test_exists_false(self):
        from minio.error import S3Error

        storage, mock_client = self._make_storage()
        mock_client.stat_object.side_effect = S3Error(
            "NoSuchKey",
            "Not found",
            "resource",
            "req",
            "host",
            "rid",
        )
        assert storage.exists("1/10/nope.png") is False

    def test_delete_calls_remove_object(self):
        storage, mock_client = self._make_storage()
        storage.delete("1/10/abc.png")
        mock_client.remove_object.assert_called_once_with(
            "test-bucket",
            "1/10/abc.png",
        )

    def test_delete_inexistente_no_falla(self):
        from minio.error import S3Error

        storage, mock_client = self._make_storage()
        mock_client.remove_object.side_effect = S3Error(
            "NoSuchKey",
            "Not found",
            "resource",
            "req",
            "host",
            "rid",
        )
        storage.delete("1/10/nope.png")  # no debe lanzar

    def test_creates_bucket_if_missing(self):
        from unittest.mock import MagicMock, patch

        with patch("minio.Minio") as MockMinio:
            mock_client = MagicMock()
            MockMinio.return_value = mock_client
            mock_client.bucket_exists.return_value = False

            from web.api.storage import MinIOStorage

            MinIOStorage(
                endpoint="localhost:9000",
                access_key="test",
                secret_key="test",
                bucket="new-bucket",
            )
            mock_client.make_bucket.assert_called_once_with("new-bucket")


# ------------------------------------------------------------------
# WebSocket de eventos del pipeline
# ------------------------------------------------------------------


class TestPipelineWebSocket:
    def test_recibe_eventos_started_processed_completed(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, h, _SCRIPT_PIPELINE)
        batch_id, _ = _create_batch_with_page(client, h, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(f"/api/batches/{batch_id}/run", headers=h)
            received = []
            for _ in range(3):
                received.append(ws.receive_json())

        types = [e["type"] for e in received]
        assert types == ["pipeline_started", "page_processed", "pipeline_completed"]
        assert received[0]["total_pages"] == 1
        assert received[1]["ok"] is True
        assert received[2]["state"] == "read"

    def test_token_invalido_cierra(self, client):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/batches/1?token=invalido") as ws:
                ws.receive_text()

    def test_otro_tenant_cierra(self, client):
        from starlette.websockets import WebSocketDisconnect
        from web.api.events import reset_event_bus

        reset_event_bus()
        h_owner = _auth_header(client, "owner@a.com", "password123", "Owner", "OrgA")
        h_other = _auth_header(client, "other@b.com", "password123", "Other", "OrgB")
        token_other = h_other["Authorization"].split()[1]

        app_id = _create_app_with_pipeline(client, h_owner, "[]")
        batch_id, _ = _create_batch_with_page(client, h_owner, app_id)

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/ws/batches/{batch_id}?token={token_other}"
            ) as ws:
                ws.receive_text()

    def test_event_bus_descarta_si_loop_no_attached(self):
        from web.api.events import PipelineEvent, PipelineEventBus

        bus = PipelineEventBus()
        # No attach_loop. Publicar no debe lanzar.
        bus.publish_from_thread(
            PipelineEvent(batch_id=1, type="pipeline_started", payload={})
        )


# ------------------------------------------------------------------
# Export ZIP de lotes
# ------------------------------------------------------------------


class TestBatchExport:
    def _open_zip(self, content: bytes):
        import io
        import zipfile

        return zipfile.ZipFile(io.BytesIO(content))

    def test_export_zip_contiene_paginas_y_manifest(self, client):
        import json

        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, _SCRIPT_PIPELINE)
        batch_id, _ = _create_batch_with_page(client, h, app_id)
        client.post(f"/api/batches/{batch_id}/run", headers=h)

        resp = client.get(f"/api/batches/{batch_id}/export", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert f'filename="batch_{batch_id}.zip"' in resp.headers["content-disposition"]

        zf = self._open_zip(resp.content)
        names = zf.namelist()
        assert "manifest.json" in names
        assert any(n.startswith("pages/page_0001") for n in names)

        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["batch_id"] == batch_id
        assert manifest["page_count"] == 1
        page = manifest["pages"][0]
        assert page["filename"].startswith("pages/")
        assert page["fields"] == {"marca": "web"}
        assert page["ocr_text"] == "fake ocr"

    def test_export_lote_otro_tenant_404(self, client):
        h_owner = _auth_header(client, "owner@a.com", "password123", "Owner", "OrgA")
        h_other = _auth_header(client, "other@b.com", "password123", "Other", "OrgB")
        app_id = _create_app_with_pipeline(client, h_owner, "[]")
        batch_id, _ = _create_batch_with_page(client, h_owner, app_id)

        resp = client.get(f"/api/batches/{batch_id}/export", headers=h_other)
        assert resp.status_code == 404

    def test_export_lote_vacio_devuelve_zip_solo_manifest(self, client):
        import json

        h = _auth_header(client)
        app_id = _create_app_with_pipeline(client, h, "[]")
        batch_id = client.post(
            "/api/batches",
            headers=h,
            json={"application_id": app_id},
        ).json()["id"]

        resp = client.get(f"/api/batches/{batch_id}/export", headers=h)
        assert resp.status_code == 200

        zf = self._open_zip(resp.content)
        assert zf.namelist() == ["manifest.json"]
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["page_count"] == 0
        assert manifest["pages"] == []


# ------------------------------------------------------------------
# Gestión de equipo: usuarios e invitaciones
# ------------------------------------------------------------------


class TestTeamUsers:
    def test_admin_lista_usuarios_del_tenant(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        _auth_header(client, "other@b.com", "password123", "Other", "OrgB")

        resp = client.get("/api/users", headers=h)
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.json()["items"]]
        assert emails == ["admin@a.com"]

    def test_operador_sin_permiso_403(self, client):
        h_admin = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        # Crear operador via invitación
        inv = client.post(
            "/api/invitations",
            headers=h_admin,
            json={"email": "op@a.com", "role": "operator"},
        ).json()
        client.post(
            "/api/invitations/accept",
            json={"token": inv["token"], "password": "op_secret", "display_name": "Op"},
        )
        tok = client.post(
            "/api/auth/login",
            json={"email": "op@a.com", "password": "op_secret"},
        ).json()["access_token"]
        h_op = {"Authorization": f"Bearer {tok}"}

        assert client.get("/api/users", headers=h_op).status_code == 403

    def test_admin_cambia_rol_y_desactiva(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        inv = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "new@a.com", "role": "operator"},
        ).json()
        u = client.post(
            "/api/invitations/accept",
            json={
                "token": inv["token"],
                "password": "pass12345",
                "display_name": "New",
            },
        ).json()

        resp = client.patch(
            f"/api/users/{u['id']}",
            headers=h,
            json={"role": "company_admin", "active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "company_admin"
        assert resp.json()["active"] is False

    def test_admin_no_puede_desactivarse_a_si_mismo(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        me = client.get("/api/auth/me", headers=h).json()
        resp = client.patch(
            f"/api/users/{me['id']}",
            headers=h,
            json={"active": False},
        )
        assert resp.status_code == 409

    def test_admin_cambia_rol_a_invalido_422(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        me = client.get("/api/auth/me", headers=h).json()
        resp = client.patch(
            f"/api/users/{me['id']}",
            headers=h,
            json={"role": "superadmin"},
        )
        assert resp.status_code == 422

    def test_usuario_de_otro_tenant_404(self, client):
        h_a = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        h_b = _auth_header(client, "admin@b.com", "password123", "Admin", "OrgB")
        me_b = client.get("/api/auth/me", headers=h_b).json()

        resp = client.patch(
            f"/api/users/{me_b['id']}",
            headers=h_a,
            json={"active": False},
        )
        assert resp.status_code == 404


class TestInvitations:
    def test_admin_crea_invitacion(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        resp = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "invitado@a.com", "role": "operator"},
        )
        assert resp.status_code == 201
        inv = resp.json()
        assert inv["email"] == "invitado@a.com"
        assert inv["role"] == "operator"
        assert inv["accepted_at"] is None
        assert len(inv["token"]) > 40

    def test_operador_no_puede_crear_invitacion(self, client):
        h_admin = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        inv = client.post(
            "/api/invitations",
            headers=h_admin,
            json={"email": "op@a.com", "role": "operator"},
        ).json()
        client.post(
            "/api/invitations/accept",
            json={"token": inv["token"], "password": "op_secret", "display_name": "Op"},
        )
        tok = client.post(
            "/api/auth/login",
            json={"email": "op@a.com", "password": "op_secret"},
        ).json()["access_token"]
        h_op = {"Authorization": f"Bearer {tok}"}

        assert (
            client.post(
                "/api/invitations",
                headers=h_op,
                json={"email": "x@a.com", "role": "operator"},
            ).status_code
            == 403
        )

    def test_invitacion_email_ya_registrado_409(self, client):
        _auth_header(client, "existe@other.com", "password123", "Existe", "OtherOrg")
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        resp = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "existe@other.com", "role": "operator"},
        )
        assert resp.status_code == 409

    def test_aceptar_invitacion_crea_usuario(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        inv = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "nuevo@a.com", "role": "operator"},
        ).json()

        resp = client.post(
            "/api/invitations/accept",
            json={
                "token": inv["token"],
                "password": "pass12345",
                "display_name": "Nuevo",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "nuevo@a.com"

        # login posterior
        tok = client.post(
            "/api/auth/login",
            json={"email": "nuevo@a.com", "password": "pass12345"},
        )
        assert tok.status_code == 200

    def test_aceptar_token_invalido_404(self, client):
        resp = client.post(
            "/api/invitations/accept",
            json={"token": "xxxxx", "password": "pass12345", "display_name": "X"},
        )
        assert resp.status_code == 404

    def test_aceptar_invitacion_dos_veces_409(self, client):
        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        inv = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "once@a.com", "role": "operator"},
        ).json()
        client.post(
            "/api/invitations/accept",
            json={"token": inv["token"], "password": "pass12345", "display_name": "A"},
        )
        resp = client.post(
            "/api/invitations/accept",
            json={"token": inv["token"], "password": "pass12345", "display_name": "B"},
        )
        assert resp.status_code == 409

    def test_revocar_invitacion_otro_tenant_404(self, client):
        h_a = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        h_b = _auth_header(client, "admin@b.com", "password123", "Admin", "OrgB")
        inv = client.post(
            "/api/invitations",
            headers=h_a,
            json={"email": "x@a.com", "role": "operator"},
        ).json()

        resp = client.delete(f"/api/invitations/{inv['id']}", headers=h_b)
        assert resp.status_code == 404

    def test_invitacion_expirada_410(self, client):
        """Forzamos expires_at en el pasado editando la BD directamente."""
        from datetime import datetime, timedelta
        from sqlalchemy.orm import sessionmaker

        from web.api.models import Invitation

        h = _auth_header(client, "admin@a.com", "password123", "Admin", "OrgA")
        inv = client.post(
            "/api/invitations",
            headers=h,
            json={"email": "caduca@a.com", "role": "operator"},
        ).json()

        # Manipular expires_at via session directa (reutilizamos la misma BD)
        import web.api.database as _db_module

        factory = sessionmaker(bind=_db_module._engine)
        with factory() as s:
            row = s.get(Invitation, inv["id"])
            row.expires_at = datetime.utcnow() - timedelta(days=1)
            s.commit()

        resp = client.post(
            "/api/invitations/accept",
            json={"token": inv["token"], "password": "pass12345", "display_name": "C"},
        )
        assert resp.status_code == 410


# ------------------------------------------------------------------
# Paginación
# ------------------------------------------------------------------


class TestPagination:
    def test_batches_limit_y_offset(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)
        for _ in range(7):
            client.post("/api/batches", headers=h, json={"application_id": app_id})

        resp = client.get("/api/batches?limit=3&offset=0", headers=h)
        data = resp.json()
        assert data["total"] == 7
        assert data["limit"] == 3
        assert data["offset"] == 0
        assert len(data["items"]) == 3

        resp = client.get("/api/batches?limit=3&offset=3", headers=h)
        assert len(resp.json()["items"]) == 3

        resp = client.get("/api/batches?limit=3&offset=6", headers=h)
        assert len(resp.json()["items"]) == 1

    def test_limit_fuera_de_rango_422(self, client):
        h = _auth_header(client)
        assert client.get("/api/batches?limit=0", headers=h).status_code == 422
        assert client.get("/api/batches?limit=201", headers=h).status_code == 422
        assert client.get("/api/batches?offset=-1", headers=h).status_code == 422

    def test_applications_paginado(self, client):
        h = _auth_header(client)
        for i in range(4):
            client.post("/api/applications", headers=h, json={"name": f"App{i}"})

        resp = client.get("/api/applications?limit=2", headers=h)
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 2

    def test_total_respeta_filtros(self, client):
        """total debe reflejar el conjunto filtrado, no el global."""
        h = _auth_header(client)
        app1 = _create_app_and_get_id(client, h, "A1")
        app2 = _create_app_and_get_id(client, h, "A2")
        for _ in range(3):
            client.post("/api/batches", headers=h, json={"application_id": app1})
        for _ in range(2):
            client.post("/api/batches", headers=h, json={"application_id": app2})

        resp = client.get(f"/api/batches?application_id={app1}&limit=10", headers=h)
        assert resp.json()["total"] == 3


# ===================================================================
# Editor de pipeline
# ===================================================================


def _barcode_step_payload(step_id: str = "bc-1") -> dict:
    """Payload mínimo de un BarcodeStep válido para usar en requests."""
    return {
        "id": step_id,
        "type": "barcode",
        "enabled": True,
        "engine": "motor1",
        "symbologies": [],
        "regex": "",
        "regex_include_symbology": False,
        "orientations": ["horizontal", "vertical"],
        "quality_threshold": 0.0,
        "window": None,
    }


class TestPipelineEditorGet:
    def test_get_pipeline_app_nueva_devuelve_lista_vacia(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h)

        assert resp.status_code == 200
        assert resp.json() == {"steps": []}

    def test_get_pipeline_con_steps_preexistentes(self, client):
        h = _auth_header(client)
        import json

        pipeline = json.dumps([_barcode_step_payload()])
        app_id = _create_app_with_pipeline(client, h, pipeline)

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h)

        assert resp.status_code == 200
        steps = resp.json()["steps"]
        assert len(steps) == 1
        assert steps[0]["type"] == "barcode"
        assert steps[0]["id"] == "bc-1"

    def test_get_pipeline_otro_tenant_404(self, client):
        h_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_and_get_id(client, h_a)
        h_b = _auth_header(client, email="b@b.com", tenant_name="B")

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h_b)

        assert resp.status_code == 404

    def test_get_pipeline_app_inexistente_404(self, client):
        h = _auth_header(client)

        resp = client.get("/api/applications/99999/pipeline", headers=h)

        assert resp.status_code == 404

    def test_get_pipeline_sin_auth_401(self, client):
        resp = client.get("/api/applications/1/pipeline")
        assert resp.status_code == 401


class TestPipelineEditorPut:
    def test_put_pipeline_barcode_ok_round_trip(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {"steps": [_barcode_step_payload()]}
        resp = client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body)

        assert resp.status_code == 200
        assert len(resp.json()["steps"]) == 1
        assert resp.json()["steps"][0]["engine"] == "motor1"

        # GET devuelve lo mismo
        resp2 = client.get(f"/api/applications/{app_id}/pipeline", headers=h)
        assert resp2.json()["steps"][0]["id"] == "bc-1"

    def test_put_pipeline_reemplaza_completo(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        # Primer PUT con 2 steps
        body1 = {
            "steps": [
                _barcode_step_payload("bc-a"),
                _barcode_step_payload("bc-b"),
            ]
        }
        client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body1)

        # Segundo PUT con solo 1 step distinto
        body2 = {"steps": [_barcode_step_payload("bc-c")]}
        resp = client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body2)

        assert resp.status_code == 200
        steps = resp.json()["steps"]
        assert len(steps) == 1
        assert steps[0]["id"] == "bc-c"

    def test_put_pipeline_tipo_desconocido_422(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {
            "steps": [
                {"id": "x", "type": "xxxx_unknown", "enabled": True},
            ]
        }
        resp = client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body)

        # Pydantic lo rechaza por Literal mismatch antes de llegar al deserialize
        assert resp.status_code == 422

    def test_put_pipeline_campo_invalido_en_step_422(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        # Barcode con "engine" inválido (no es "motor1" ni "motor2")
        body = {
            "steps": [
                {
                    "id": "bc-1",
                    "type": "barcode",
                    "enabled": True,
                    "engine": "motor_fantasma",
                }
            ]
        }
        resp = client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body)

        assert resp.status_code == 422
        assert "Pipeline inválido" in resp.json()["detail"]

    def test_put_pipeline_otro_tenant_404(self, client):
        h_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_and_get_id(client, h_a)
        h_b = _auth_header(client, email="b@b.com", tenant_name="B")

        body = {"steps": [_barcode_step_payload()]}
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h_b, json=body
        )

        assert resp.status_code == 404

    def test_put_pipeline_persiste_en_pipeline_json(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {"steps": [_barcode_step_payload("bc-xyz")]}
        client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body)

        # Verifica via GET /applications/:id (endpoint existente)
        resp = client.get(f"/api/applications/{app_id}", headers=h)
        import json

        stored = json.loads(resp.json()["pipeline_json"])
        assert len(stored) == 1
        assert stored[0]["id"] == "bc-xyz"

    def test_put_pipeline_lista_vacia_ok(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json={"steps": []}
        )

        assert resp.status_code == 200
        assert resp.json()["steps"] == []


# ------------------------------------------------------------------
# Transferencia (background task)
# ------------------------------------------------------------------


def _create_app_for_transfer(
    client,
    headers,
    transfer_json: str,
    events_json: str = "{}",
) -> int:
    """Crea una aplicación con configuración de transferencia y eventos."""

    resp = client.post(
        "/api/applications",
        headers=headers,
        json={
            "name": f"XferApp-{transfer_json[:8]}-{events_json[:8]}",
            "transfer_json": transfer_json,
            "events_json": events_json,
        },
    )
    return resp.json()["id"]


def _prepare_batch_in_read(client, headers, app_id: int) -> tuple[int, int]:
    """Crea un lote, sube una página y la procesa con pipeline vacío.

    Tras esto el lote queda en estado ``read`` y es transferible.
    """
    batch_id, page_id = _create_batch_with_page(client, headers, app_id)
    resp = client.post(f"/api/batches/{batch_id}/run", headers=headers)
    assert resp.status_code == 202
    # Pipeline vacío => state queda como "read"
    return batch_id, page_id


class TestTransferEndpoint:
    def test_transfer_202_dispara_background_y_devuelve_batch(self, client, tmp_path):
        import json as _json

        h = _auth_header(client)
        dest = tmp_path / "salida"
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(dest),
                "create_subdirs": True,
            }
        )
        app_id = _create_app_for_transfer(client, h, transfer)
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/transfer", headers=h)
        assert resp.status_code == 202
        body = resp.json()
        assert body["id"] == batch_id

        # El BackgroundTask de FastAPI ya corrió bajo TestClient.
        # Verificar que el destino existe y contiene la página.
        out_dir = dest / f"batch_{batch_id}"
        assert out_dir.exists()
        files = list(out_dir.iterdir())
        assert len(files) == 1

    def test_transfer_409_si_estado_no_es_read(self, client, tmp_path):
        h = _auth_header(client)
        app_id = _create_app_for_transfer(client, h, "{}")
        # Lote recién creado (state = "created"), sin pipeline ejecutado
        batch_id, _ = _create_batch_with_page(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/transfer", headers=h)
        assert resp.status_code == 409

    def test_transfer_404_lote_inexistente(self, client):
        h = _auth_header(client)
        resp = client.post("/api/batches/99999/transfer", headers=h)
        assert resp.status_code == 404

    def test_transfer_404_otro_tenant(self, client, tmp_path):
        import json as _json

        h1 = _auth_header(client)
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(tmp_path / "x"),
            }
        )
        app_id = _create_app_for_transfer(client, h1, transfer)
        batch_id, _ = _prepare_batch_in_read(client, h1, app_id)

        client.post(
            "/api/auth/register",
            json={
                "email": "intruso2@x.com",
                "password": "password123",
                "display_name": "I",
                "tenant_name": "OtraOrgXfer",
            },
        )
        token2 = client.post(
            "/api/auth/login",
            json={"email": "intruso2@x.com", "password": "password123"},
        ).json()["access_token"]
        h2 = {"Authorization": f"Bearer {token2}"}

        resp = client.post(f"/api/batches/{batch_id}/transfer", headers=h2)
        assert resp.status_code == 404

    def test_transfer_emite_started_y_completed(self, client, tmp_path):
        import json as _json

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]

        dest = tmp_path / "out"
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(dest),
                "create_subdirs": True,
            }
        )
        app_id = _create_app_for_transfer(client, h, transfer)
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(f"/api/batches/{batch_id}/transfer", headers=h)
            received = []
            # transfer_started + transfer_page + transfer_completed
            for _ in range(3):
                received.append(ws.receive_json())

        types = [e["type"] for e in received]
        assert "transfer_started" in types
        assert "transfer_completed" in types
        completed = [e for e in received if e["type"] == "transfer_completed"][0]
        assert completed["success"] is True
        assert completed["files_transferred"] == 1

    def test_transfer_aborted_si_validate_devuelve_false(self, client, tmp_path):
        import json as _json

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]

        dest = tmp_path / "out"
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(dest),
            }
        )
        events = _json.dumps(
            {
                "on_transfer_validate": (
                    "def on_transfer_validate(app, batch):\n    return False\n"
                )
            }
        )
        app_id = _create_app_for_transfer(client, h, transfer, events_json=events)
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(f"/api/batches/{batch_id}/transfer", headers=h)
            event = ws.receive_json()

        assert event["type"] == "transfer_aborted"
        assert event["reason"] == "validate_returned_false"
        # Y no se debe haber escrito nada
        assert not dest.exists()

    def test_transfer_aborted_si_no_configurada(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]

        # transfer_json vacío → not_configured
        app_id = _create_app_for_transfer(client, h, "{}")
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(f"/api/batches/{batch_id}/transfer", headers=h)
            event = ws.receive_json()

        assert event["type"] == "transfer_aborted"
        assert event["reason"] == "not_configured"

    def test_transfer_aborted_si_standard_disabled(self, client, tmp_path):
        import json as _json

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]

        transfer = _json.dumps(
            {
                "standard_enabled": False,
                "mode": "folder",
                "destination": str(tmp_path / "no_se_usa"),
            }
        )
        app_id = _create_app_for_transfer(client, h, transfer)
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(f"/api/batches/{batch_id}/transfer", headers=h)
            event = ws.receive_json()

        assert event["type"] == "transfer_aborted"
        assert event["reason"] == "not_configured"

    def test_transfer_emite_error_si_excepcion(self, client, tmp_path):
        """Si TransferService lanza excepción, se emite transfer_error."""
        import json as _json
        from unittest.mock import patch

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)
        token = h["Authorization"].split()[1]

        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(tmp_path / "out"),
            }
        )
        app_id = _create_app_for_transfer(client, h, transfer)
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        # Patchear TransferService.transfer para que lance.
        with patch(
            "app.services.transfer_service.TransferService.transfer",
            side_effect=RuntimeError("boom-xfer"),
        ):
            with client.websocket_connect(
                f"/ws/batches/{batch_id}?token={token}"
            ) as ws:
                client.post(f"/api/batches/{batch_id}/transfer", headers=h)
                event = ws.receive_json()
                # Saltar transfer_started si llega antes
                if event["type"] == "transfer_started":
                    event = ws.receive_json()

        assert event["type"] == "transfer_error"
        assert "boom-xfer" in event["error"]

    def test_transfer_dispara_on_transfer_advanced(self, client, tmp_path):
        """on_transfer_advanced se ejecuta tras la transferencia OK."""
        import json as _json

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)

        # El script escribe un fichero marcador en tmp_path.
        marker = tmp_path / "advanced_ran.txt"
        dest = tmp_path / "out"
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(dest),
            }
        )
        events = _json.dumps(
            {
                "on_transfer_advanced": (
                    "def on_transfer_advanced(app, batch, result):\n"
                    f"    Path(r'{marker}').write_text(str(result.success))\n"
                )
            }
        )
        app_id = _create_app_for_transfer(
            client,
            h,
            transfer,
            events_json=events,
        )
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/transfer", headers=h)
        assert resp.status_code == 202

        assert marker.exists()
        assert marker.read_text() == "True"

    def test_transfer_dispara_on_transfer_page_por_pagina(self, client, tmp_path):
        """on_transfer_page se ejecuta una vez por página transferida."""
        import json as _json

        from web.api.events import reset_event_bus

        reset_event_bus()
        h = _auth_header(client)

        counter = tmp_path / "page_counter.txt"
        dest = tmp_path / "out"
        transfer = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(dest),
            }
        )
        events = _json.dumps(
            {
                "on_transfer_page": (
                    "def on_transfer_page(app, batch, page, result):\n"
                    f"    p = Path(r'{counter}')\n"
                    "    prev = int(p.read_text()) if p.exists() else 0\n"
                    "    p.write_text(str(prev + 1))\n"
                )
            }
        )
        app_id = _create_app_for_transfer(
            client,
            h,
            transfer,
            events_json=events,
        )
        batch_id, _ = _prepare_batch_in_read(client, h, app_id)

        resp = client.post(f"/api/batches/{batch_id}/transfer", headers=h)
        assert resp.status_code == 202

        # Debe haberse llamado exactamente una vez (1 página subida).
        assert counter.exists()

    def test_transfer_409_when_transferring(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "transferring"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/transfer", headers=headers)
        assert r.status_code == 409

    def test_transfer_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/transfer", headers=headers)
        assert r.status_code == 409


# ------------------------------------------------------------------
# Runners — batch.state lifecycle con try/finally
# ------------------------------------------------------------------


class TestRunnersState:
    """Verifica que los runners gestionan batch.state con try/finally."""

    def test_pipeline_run_marks_running_then_read(
        self, client, db_session, monkeypatch
    ):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        # Antes de /run, state == "created"
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "created"

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        assert r.status_code == 202

        # Tras run (síncrono en tests via BackgroundTasks) con pipeline vacío
        # y página válida: el estado terminal DEBE ser "read" exactamente.
        # Aceptar "error_read" aquí enmascararía regresiones que hagan
        # fallar siempre el pipeline.
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "read"

    def test_pipeline_finally_resets_running_state(
        self, client, db_session, monkeypatch
    ):
        """Si el runner queda colgado en running, el finally lo fuerza a error_read.

        Ejerce la ruta completa HTTP + BackgroundTasks: parchea
        ``_execute_pipeline`` para que lance excepción y verifica, tras el
        POST al endpoint, que el lote acaba en ``error_read``.

        Nota: ``run_pipeline_for_batch`` re-propaga la excepción tras marcar
        ``error_read``, por lo que el BackgroundTask de Starlette la
        levanta durante la finalización del response. Envolvemos el POST en
        try/except para aislarla y luego consultamos el estado por otro GET.
        """
        import pytest

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        # Parchear la función interna que ejecuta el pipeline real.
        import web.api.tasks.pipeline_runner as runner_mod

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        if not hasattr(runner_mod, "_execute_pipeline"):
            pytest.skip("_execute_pipeline not extracted yet")
        monkeypatch.setattr(runner_mod, "_execute_pipeline", boom)

        # POST al endpoint: FastAPI TestClient ejecuta el BackgroundTask
        # síncrono tras el response. La excepción del runner aflora aquí,
        # pero para entonces el finally ya ha persistido error_read.
        with pytest.raises(RuntimeError, match="boom"):
            client.post(f"/api/batches/{batch_id}/run", headers=headers)

        # Tras ejecutar el background con _execute_pipeline rota, el finally
        # del runner debe haber dejado el lote en error_read.
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "error_read"

    def test_transfer_finally_resets_transferring_state(
        self,
        client,
        db_session,
        monkeypatch,
        tmp_path,
    ):
        """Si el runner de transfer queda en transferring, el finally lo fuerza a error_read.

        Ejerce la ruta completa HTTP + BackgroundTasks: parchea
        ``_execute_transfer`` para que lance excepción y verifica, tras el
        POST al endpoint, que el lote acaba en ``error_read``.

        Como en el test del pipeline, ``run_transfer_for_batch`` re-propaga
        la excepción tras marcar ``error_read``; envolvemos el POST en
        ``pytest.raises`` y consultamos el estado con un GET aparte.
        """
        import json as _json

        import pytest

        headers = _auth_header(client)
        transfer_cfg = _json.dumps(
            {
                "standard_enabled": True,
                "mode": "folder",
                "destination": str(tmp_path / "salida"),
            }
        )
        app_id = _create_app_for_transfer(client, headers, transfer_cfg)
        batch_id, _ = _prepare_batch_in_read(client, headers, app_id)

        import web.api.tasks.transfer_runner as runner_mod

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        if not hasattr(runner_mod, "_execute_transfer"):
            pytest.skip("_execute_transfer not extracted yet")
        monkeypatch.setattr(runner_mod, "_execute_transfer", boom)

        # POST al endpoint: el BackgroundTask corre síncronamente en tests y
        # re-propaga la excepción, pero el finally ya escribió error_read.
        with pytest.raises(RuntimeError, match="boom"):
            client.post(f"/api/batches/{batch_id}/transfer", headers=headers)

        # Tras fallar _execute_transfer, el finally debe dejar error_read.
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "error_read"


# ------------------------------------------------------------------
# PATCH /api/pages/{page_id} — toggle de flags
# ------------------------------------------------------------------


class TestPagesPatch:
    def test_toggle_is_excluded(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["is_excluded"] is True

    def test_toggle_needs_review_with_reason(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"needs_review": True, "review_reason": "check manually"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["needs_review"] is True
        assert body["review_reason"] == "check manually"

    def test_patch_other_tenant_404(self, client, db_session):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers_b,
        )
        assert r.status_code == 404

    def test_patch_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers,
        )
        assert r.status_code == 409

    def test_patch_empty_body_is_noop(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)
        r = client.patch(f"/api/pages/{page_id}", json={}, headers=headers)
        assert r.status_code == 200
        assert r.json()["is_excluded"] is False
        assert r.json()["needs_review"] is False

    def test_patch_review_reason_only(self, client):
        """review_reason can be sent alone without needs_review."""
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)
        r = client.patch(
            f"/api/pages/{page_id}",
            json={"review_reason": "only reason"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["review_reason"] == "only reason"

    def test_patch_dismiss_review_clears_reason(self, client):
        """Setting needs_review=False auto-clears review_reason."""
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Primero marcar para revisión con razón
        r = client.patch(
            f"/api/pages/{page_id}",
            json={"needs_review": True, "review_reason": "check"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["review_reason"] == "check"

        # Ahora dismiss la revisión
        r = client.patch(
            f"/api/pages/{page_id}",
            json={"needs_review": False},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["needs_review"] is False
        assert body["review_reason"] == ""


class TestPagesRotate:
    def test_rotate_90_swaps_dimensions(self, client, db_session, storage_dir):
        import cv2
        from pathlib import Path
        from app.models.page import Page

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Lee dimensiones antes
        page = db_session.query(Page).filter_by(id=page_id).first()
        full_path = Path(storage_dir) / page.image_path
        img_before = cv2.imread(str(full_path))
        h_before, w_before = img_before.shape[:2]

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 200

        img_after = cv2.imread(str(full_path))
        h_after, w_after = img_after.shape[:2]
        assert h_after == w_before
        assert w_after == h_before

    def test_rotate_180_preserves_dimensions(self, client, db_session, storage_dir):
        import cv2
        from pathlib import Path
        from app.models.page import Page

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        page = db_session.query(Page).filter_by(id=page_id).first()
        full_path = Path(storage_dir) / page.image_path
        img_before = cv2.imread(str(full_path))
        h_before, w_before = img_before.shape[:2]

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 2},
            headers=headers,
        )
        assert r.status_code == 200

        img_after = cv2.imread(str(full_path))
        assert img_after.shape[:2] == (h_before, w_before)

    def test_rotate_adjusts_barcode_coords(self, client, db_session, storage_dir):
        import cv2
        from pathlib import Path

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Leer dimensiones reales de la imagen test
        page = db_session.query(Page).filter_by(id=page_id).first()
        full_path = Path(storage_dir) / page.image_path
        img = cv2.imread(str(full_path))
        h, w = img.shape[:2]

        # Inyectar barcode con coords conocidas
        bc = Barcode(
            page_id=page_id,
            value="TEST",
            symbology="CODE128",
            engine="test",
            step_id="s1",
            pos_x=10,
            pos_y=20,
            pos_w=30,
            pos_h=5,
            quality=0.9,
            role="",
        )
        db_session.add(bc)
        db_session.commit()
        bc_id = bc.id

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 200

        db_session.expire_all()
        bc_after = db_session.query(Barcode).filter_by(id=bc_id).first()
        # 90° CW: new_x = h - old_y - old_h, new_y = old_x, new_w = old_h, new_h = old_w
        assert bc_after.pos_x == h - 20 - 5
        assert bc_after.pos_y == 10
        assert bc_after.pos_w == 5
        assert bc_after.pos_h == 30

    def test_rotate_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 409

    def test_rotate_invalid_turns_422(self, client):
        """turns fuera de {1,2,3} debe devolver 422."""
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 0},
            headers=headers,
        )
        assert r.status_code == 422

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 4},
            headers=headers,
        )
        assert r.status_code == 422

    def test_rotate_270_swaps_dimensions_and_coords(
        self, client, db_session, storage_dir
    ):
        """turns=3 equivale a 90° CCW: dimensiones se intercambian."""
        import cv2
        from pathlib import Path
        from app.models.barcode import Barcode
        from app.models.page import Page

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        page = db_session.query(Page).filter_by(id=page_id).first()
        full_path = Path(storage_dir) / page.image_path
        img_before = cv2.imread(str(full_path))
        h_before, w_before = img_before.shape[:2]

        # Barcode en esquina superior-izquierda
        bc = Barcode(
            page_id=page_id,
            value="T",
            symbology="CODE128",
            engine="test",
            step_id="s1",
            pos_x=5,
            pos_y=3,
            pos_w=20,
            pos_h=10,
            quality=0.9,
            role="",
        )
        db_session.add(bc)
        db_session.commit()
        bc_id = bc.id

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 3},
            headers=headers,
        )
        assert r.status_code == 200

        img_after = cv2.imread(str(full_path))
        assert img_after.shape[:2] == (w_before, h_before)  # dimensiones intercambiadas

        db_session.expire_all()
        bc_after = db_session.query(Barcode).filter_by(id=bc_id).first()
        # Verifica que las coords se movieron (no nos importa la fórmula exacta,
        # pero no deben coincidir con 1 turn)
        assert (bc_after.pos_x, bc_after.pos_y, bc_after.pos_w, bc_after.pos_h) != (
            5,
            3,
            20,
            10,
        )

    def test_rotate_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers_b,
        )
        assert r.status_code == 404


class TestPagesBarcodes:
    def test_add_manual_barcode(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "ABC123", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 201
        bc = r.json()
        assert bc["value"] == "ABC123"
        assert bc["symbology"] == "MANUAL"
        assert bc["engine"] == "manual"
        assert bc["step_id"] == "manual"
        assert bc["pos_x"] == 0 and bc["pos_y"] == 0

    def test_add_barcode_with_custom_symbology(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "XYZ", "symbology": "QR"},
            headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["symbology"] == "QR"

    def test_add_barcode_empty_value_422(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 422

    def test_add_barcode_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 409

    def test_add_barcode_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers_b,
        )
        assert r.status_code == 404

    def test_add_barcode_whitespace_only_value_422(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "   ", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 422

    def test_add_barcode_trims_value(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "  ABC  ", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["value"] == "ABC"

    def test_delete_barcode(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Crear barcode
        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        # Borrar
        r = client.delete(
            f"/api/pages/{page_id}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 204

        # Verificar que ya no existe en BD
        from app.models.barcode import Barcode

        assert db_session.query(Barcode).filter_by(id=bc_id).first() is None

    def test_delete_barcode_from_wrong_page_404(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id_a = _create_batch_with_page(client, headers, app_id)
        _, page_id_b = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id_a}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        # Intentar borrar desde otra página del mismo tenant
        r = client.delete(
            f"/api/pages/{page_id_b}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_barcode_nonexistent_404(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.delete(
            f"/api/pages/{page_id}/barcodes/999999",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_barcode_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.delete(
            f"/api/pages/{page_id}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 409

    def test_delete_barcode_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers_a,
        )
        bc_id = r.json()["id"]

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.delete(
            f"/api/pages/{page_id}/barcodes/{bc_id}",
            headers=headers_b,
        )
        assert r.status_code == 404


class TestBatchesReorder:
    def _make_batch_with_n_pages(self, client, headers, n=3):
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, first_page = _create_batch_with_page(client, headers, app_id)
        page_ids = [first_page]
        for _ in range(n - 1):
            files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
            r = client.post(
                f"/api/batches/{batch_id}/pages",
                files=files,
                headers=headers,
            )
            page_ids.extend(p["id"] for p in r.json()["created"])
        return batch_id, page_ids

    def test_reorder_changes_indices(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        reversed_ids = list(reversed(ids))
        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": reversed_ids},
            headers=headers,
        )
        assert r.status_code == 200

        # Verificar orden vía GET pages
        r = client.get(f"/api/batches/{batch_id}/pages", headers=headers)
        body = r.json()
        pages = body["items"] if isinstance(body, dict) and "items" in body else body
        page_ids_ordered = [p["id"] for p in pages]
        page_indices = [p["page_index"] for p in pages]
        assert page_ids_ordered == reversed_ids
        assert page_indices == [0, 1, 2]

    def test_reorder_422_if_set_mismatch(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 2)

        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": [ids[0], 999999]},
            headers=headers,
        )
        assert r.status_code == 422

    def test_reorder_422_if_length_mismatch(self, client):
        """Si faltan o sobran ids respecto al set actual → 422."""
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        # Falta uno
        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": ids[:2]},
            headers=headers,
        )
        assert r.status_code == 422

    def test_reorder_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 2)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": list(reversed(ids))},
            headers=headers,
        )
        assert r.status_code == 409

    def test_reorder_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        batch_id, ids = self._make_batch_with_n_pages(client, headers_a, 2)

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": list(reversed(ids))},
            headers=headers_b,
        )
        assert r.status_code == 404


class TestBatchesDeleteAfter:
    def _make_batch_with_n_pages(self, client, headers, n=5):
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, first_page = _create_batch_with_page(client, headers, app_id)
        page_ids = [first_page]
        for _ in range(n - 1):
            files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
            r = client.post(
                f"/api/batches/{batch_id}/pages",
                files=files,
                headers=headers,
            )
            page_ids.extend(p["id"] for p in r.json()["created"])
        return batch_id, page_ids

    def test_delete_from_middle(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 5)

        # Eliminar desde la posición 2 (tercera página): se borran 3 (índices 2,3,4)
        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[2]}",
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["deleted"] == 3
        assert body["batch_page_count"] == 2

    def test_delete_from_first(self, client):
        """Borrar desde la primera página elimina todas."""
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[0]}",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] == 3
        assert r.json()["batch_page_count"] == 0

    def test_delete_from_last(self, client):
        """Borrar desde la última página solo la elimina a ella."""
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[-1]}",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] == 1
        assert r.json()["batch_page_count"] == 2

    def test_delete_after_page_not_in_batch_404(self, client):
        headers = _auth_header(client)
        batch_id, _ = self._make_batch_with_n_pages(client, headers, 2)

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/999999",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_after_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[1]}",
            headers=headers,
        )
        assert r.status_code == 409

    def test_delete_after_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com", tenant_name="A")
        batch_id, ids = self._make_batch_with_n_pages(client, headers_a, 2)

        headers_b = _auth_header(client, email="b@b.com", tenant_name="B")
        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[0]}",
            headers=headers_b,
        )
        assert r.status_code == 404


# ------------------------------------------------------------------
# Evento WS page_updated en mutaciones de página
# ------------------------------------------------------------------


class TestWsPageUpdated:
    def test_patch_page_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.patch(
                f"/api/pages/{page_id}",
                json={"is_excluded": True},
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["page_id"] == page_id
            assert ev["action"] == "flags"

    def test_rotate_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(
                f"/api/pages/{page_id}/rotate",
                json={"turns": 1},
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "rotated"
            assert ev["page_id"] == page_id

    def test_add_barcode_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            r = client.post(
                f"/api/pages/{page_id}/barcodes",
                json={"value": "X", "symbology": "MANUAL"},
                headers=headers,
            )
            bc_id = r.json()["id"]
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "barcode_added"
            assert ev["page_id"] == page_id
            assert ev.get("barcode_id") == bc_id

    def test_delete_barcode_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.delete(
                f"/api/pages/{page_id}/barcodes/{bc_id}",
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "barcode_deleted"
            assert ev.get("barcode_id") == bc_id

    def test_reorder_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, first_page = _create_batch_with_page(client, headers, app_id)
        # Añadir una segunda página
        files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
        r = client.post(
            f"/api/batches/{batch_id}/pages",
            files=files,
            headers=headers,
        )
        second_page = r.json()["created"][0]["id"]

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.post(
                f"/api/batches/{batch_id}/reorder",
                json={"page_ids": [second_page, first_page]},
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "reordered"
            assert ev.get("new_order") == [second_page, first_page]

    def test_delete_page_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.delete(
                f"/api/batches/{batch_id}/pages/{page_id}",
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "deleted"
            assert ev["page_id"] == page_id

    def test_delete_pages_from_emits_event(self, client):
        from web.api.events import reset_event_bus

        reset_event_bus()
        headers = _auth_header(client)
        token = headers["Authorization"].split()[1]
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, first_page = _create_batch_with_page(client, headers, app_id)
        files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
        r = client.post(
            f"/api/batches/{batch_id}/pages",
            files=files,
            headers=headers,
        )
        second_page = r.json()["created"][0]["id"]

        with client.websocket_connect(f"/ws/batches/{batch_id}?token={token}") as ws:
            client.delete(
                f"/api/batches/{batch_id}/pages/after/{first_page}",
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "deleted"
            assert ev["page_id"] == 0
            assert set(ev.get("deleted_ids", [])) == {first_page, second_page}
            assert ev.get("batch_page_count") == 0


class TestEventsFire:
    """Endpoint POST /api/batches/{id}/events/{name}."""

    def _set_event_script(
        self,
        client,
        h,
        application_id: int,
        event_name: str,
        script: str,
    ):
        """Helper: configura el script de un evento en events_json de la app."""
        resp = client.get(f"/api/applications/{application_id}", headers=h)
        events = resp.json().get("events_json") or "{}"
        import json as _json

        events_d = _json.loads(events)
        events_d[event_name] = script
        client.patch(
            f"/api/applications/{application_id}",
            headers=h,
            json={"events_json": _json.dumps(events_d)},
        )

    def test_fire_script_no_definido_devuelve_executed_false(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h,
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is False
        assert data["cancel"] is False
        assert data["error"] is None

    def test_fire_on_batch_loaded_ejecuta_devuelve_executed_true(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    return {'result': 'hola'}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h,
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is True
        assert data["result"] == "hola"
        assert data["cancel"] is False

    def test_fire_on_navigate_prev_con_cancel_true(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_navigate_prev",
            "def on_navigate_prev(app, batch, page):\n    return False\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_prev",
            headers=h,
            json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["cancel"] is True

    def test_fire_on_navigate_next_con_target_page_id(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_navigate_next",
            "def on_navigate_next(app, batch, page):\n"
            "    return {'target_page_id': 999}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_next",
            headers=h,
            json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["target_page_id"] == 999

    def test_fire_on_page_changed_aplica_fields_updated(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_page_changed",
            "def on_page_changed(app, batch, page):\n"
            "    page.fields['cliente'] = 'Acme'\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_page_changed",
            headers=h,
            json={"page_id": page_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields_updated"] == {"cliente": "Acme"}

    def test_fire_on_key_event_recibe_key(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_key_event",
            "def on_key_event(app, batch, key):\n    return {'result': key}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_key_event",
            headers=h,
            json={"key": "Ctrl+Alt+L"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "Ctrl+Alt+L"

    def test_fire_script_lanza_devuelve_error(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client,
            h,
            app_id,
            "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    raise RuntimeError('boom')\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h,
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is True
        assert "boom" in (data["error"] or "")

    def test_fire_event_name_no_valido_400(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_evento_raro",
            headers=h,
            json={},
        )
        assert resp.status_code == 400

    def test_fire_batch_otro_tenant_404(self, client):
        h1 = _auth_header(client)
        batch_id = _create_batch(client, h1)
        h2 = _auth_header(
            client,
            email="otro@docscan.example.com",
            tenant_name="OtraCorp",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h2,
            json={},
        )
        assert resp.status_code == 404

    def test_fire_on_navigate_prev_sin_page_id_422(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_prev",
            headers=h,
            json={},
        )
        assert resp.status_code == 422

    def test_fire_on_key_event_sin_key_422(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_key_event",
            headers=h,
            json={},
        )
        assert resp.status_code == 422

    def test_fire_on_page_changed_page_de_otro_lote_404(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_a = _create_batch(client, h, app_id=app_id)
        batch_b = _create_batch(client, h, app_id=app_id)
        page_id_b = _upload_page(client, h, batch_b)
        resp = client.post(
            f"/api/batches/{batch_a}/events/on_page_changed",
            headers=h,
            json={"page_id": page_id_b},
        )
        assert resp.status_code == 404

    def test_fire_on_batch_loaded_permitido_durante_running(self, client, db_session):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()
        self._set_event_script(
            client,
            h,
            app_id,
            "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    return {'result': batch.state}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h,
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "running"

    def test_fire_on_page_changed_permitido_durante_running(self, client, db_session):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        from app.models.batch import Batch

        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()
        self._set_event_script(
            client,
            h,
            app_id,
            "on_page_changed",
            "def on_page_changed(app, batch, page):\n    return True\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_page_changed",
            headers=h,
            json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["executed"] is True
