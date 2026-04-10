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
                "password": "pass123",
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
                "password": "pass123",
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
                "password": "pass123",
            },
        )
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
    password: str = "pass",
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
        assert resp.json() == []

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
        assert len(resp.json()) == 2

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
                "password": "pass",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "pass",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Tenant 2 no ve las apps de tenant 1
        resp = client.get("/api/applications", headers=h2)
        assert resp.json() == []

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
        assert resp.json() == []

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
        assert len(resp.json()) == 2

    def test_filtrar_por_aplicacion(self, client):
        h = _auth_header(client)
        app1 = _create_app_and_get_id(client, h, "A1")
        app2 = _create_app_and_get_id(client, h, "A2")
        client.post("/api/batches", headers=h, json={"application_id": app1})
        client.post("/api/batches", headers=h, json={"application_id": app1})
        client.post("/api/batches", headers=h, json={"application_id": app2})
        resp = client.get(f"/api/batches?application_id={app1}", headers=h)
        assert len(resp.json()) == 2
        resp = client.get(f"/api/batches?application_id={app2}", headers=h)
        assert len(resp.json()) == 1

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
        assert len(resp.json()) == 1
        resp = client.get("/api/batches?state=created", headers=h)
        assert len(resp.json()) == 1

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
                "password": "pass",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "pass",
            },
        )
        h2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = client.get("/api/batches", headers=h2)
        assert resp.json() == []

        resp = client.get(f"/api/batches/{created['id']}", headers=h2)
        assert resp.status_code == 404

    def test_no_crea_lote_en_app_de_otro_tenant(self, client):
        h1 = _auth_header(client)
        app_id = _create_app_and_get_id(client, h1)

        client.post(
            "/api/auth/register",
            json={
                "email": "otro@otro.com",
                "password": "pass",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "pass",
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


def _create_batch(client, headers) -> int:
    """Crea una aplicación y un lote vacío. Devuelve batch_id."""
    app_id = _create_app_and_get_id(client, headers)
    resp = client.post(
        "/api/batches",
        headers=headers,
        json={
            "application_id": app_id,
        },
    )
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
                "password": "pass",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "pass",
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
                "password": "pass",
                "display_name": "Otro",
                "tenant_name": "OtraCorp",
            },
        )
        resp2 = client.post(
            "/api/auth/login",
            json={
                "email": "otro@otro.com",
                "password": "pass",
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
                "password": "p",
                "display_name": "I",
                "tenant_name": "OtraCorpRun",
            },
        )
        token = client.post(
            "/api/auth/login",
            json={
                "email": "intruso@x.com",
                "password": "p",
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
