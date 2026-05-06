"""Tests del router /api/admin/tenants (Hito 5 sprint superadmin).

Cubre auth, listado, creación, detalle, actualización y borrado
hard-cascade. Incluye verificación de audit_logs y de los guards
especiales (tenant TecnoMedia, lotes activos, slug reservado).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
import web.api._register_models  # noqa: F401  registra todas las tablas

import web.api.database as _db_module
from web.api.bootstrap import bootstrap_superadmin
from web.api.database import get_db
from web.api.main import create_app
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_OPERATOR,
    AuditLog,
    Tenant,
    User,
)
from web.api.storage import FilesystemStorage, get_storage


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
    _db_module._engine = engine
    yield engine
    _db_module._engine = None
    _db_module._SessionFactory = None
    engine.dispose()


@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / "storage"


@pytest.fixture
def client(_test_engine, storage_dir):
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
    app.state.test_db_factory = factory
    app.state.test_storage_dir = storage_dir
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _superadmin_header(
    client: TestClient,
    *,
    email: str = "superadmin@tecnomedia.es",
    password: str = "superpass123",
    display: str = "SA",
) -> dict[str, str]:
    """Crea (idempotente) un superadmin TecnoMedia y devuelve su Authorization."""
    factory = client.app.state.test_db_factory
    with factory() as db:
        bootstrap_superadmin(db, email=email, password=password, display_name=display)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_tenant_and_user(
    factory,
    *,
    tenant_name: str,
    tenant_slug: str | None = None,
    user_email: str,
    user_password: str = "userpass123",
    user_role: str = ROLE_COMPANY_ADMIN,
    plan: str = "free",
    active: bool = True,
) -> tuple[int, int]:
    """Inserta Tenant + User vía BD y devuelve (tenant_id, user_id)."""
    from web.api.auth.security import hash_password

    slug = tenant_slug or tenant_name.lower().replace(" ", "-")
    with factory() as db:
        tenant = Tenant(name=tenant_name, slug=slug, plan=plan, active=active)
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email=user_email,
            hashed_password=hash_password(user_password),
            display_name=user_email,
            role=user_role,
            active=True,
        )
        db.add(user)
        db.commit()
        return tenant.id, user.id


def _company_admin_header(
    client: TestClient,
    *,
    email: str = "admin@tenanta.com",
    password: str = "userpass123",
) -> dict[str, str]:
    _create_tenant_and_user(
        client.app.state.test_db_factory,
        tenant_name="TenantA",
        user_email=email,
        user_password=password,
        user_role=ROLE_COMPANY_ADMIN,
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _operator_header(client: TestClient) -> dict[str, str]:
    _create_tenant_and_user(
        client.app.state.test_db_factory,
        tenant_name="TenantOp",
        user_email="op@tenantop.com",
        user_password="userpass123",
        user_role=ROLE_OPERATOR,
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "op@tenantop.com", "password": "userpass123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# --------------------------------------------------------------------
# Auth y RBAC
# --------------------------------------------------------------------


class TestAdminTenantsAuth:
    def test_sin_token_401(self, client):
        resp = client.get("/api/admin/tenants")
        assert resp.status_code == 401

    def test_company_admin_403(self, client):
        h = _company_admin_header(client)
        resp = client.get("/api/admin/tenants", headers=h)
        assert resp.status_code == 403

    def test_operator_403(self, client):
        h = _operator_header(client)
        resp = client.get("/api/admin/tenants", headers=h)
        assert resp.status_code == 403

    def test_superadmin_200(self, client):
        h = _superadmin_header(client)
        resp = client.get("/api/admin/tenants", headers=h)
        assert resp.status_code == 200


# --------------------------------------------------------------------
# List
# --------------------------------------------------------------------


class TestAdminTenantsList:
    def test_lista_incluye_tecnomedia(self, client):
        h = _superadmin_header(client)
        resp = client.get("/api/admin/tenants", headers=h)
        data = resp.json()
        slugs = {t["slug"] for t in data["items"]}
        assert "tecnomedia" in slugs

    def test_lista_incluye_stats(self, client):
        h = _superadmin_header(client)
        _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="StatTest",
            user_email="a@b.c",
        )
        resp = client.get("/api/admin/tenants", headers=h)
        items = resp.json()["items"]
        stat_test = next(t for t in items if t["slug"] == "stattest")
        assert stat_test["stats"]["n_users"] == 1
        assert stat_test["stats"]["n_applications"] == 0
        assert stat_test["stats"]["n_batches"] == 0

    def test_paginated(self, client):
        h = _superadmin_header(client)
        for i in range(5):
            _create_tenant_and_user(
                client.app.state.test_db_factory,
                tenant_name=f"Org{i}",
                user_email=f"u{i}@o.com",
            )
        resp = client.get("/api/admin/tenants?limit=3&offset=0", headers=h)
        data = resp.json()
        assert data["total"] >= 6  # 5 + tecnomedia
        assert len(data["items"]) == 3


# --------------------------------------------------------------------
# Create
# --------------------------------------------------------------------


class TestAdminTenantsCreate:
    def _payload(self, **kw):
        return {
            "tenant_name": kw.get("tenant_name", "ACME"),
            "plan": kw.get("plan", "free"),
            "admin_email": kw.get("admin_email", "admin@acme.com"),
            "admin_password": kw.get("admin_password", "password123"),
            "admin_display_name": kw.get("admin_display_name", "Admin ACME"),
        }

    def test_crea_tenant_y_admin_201(self, client):
        h = _superadmin_header(client)
        resp = client.post("/api/admin/tenants", headers=h, json=self._payload())
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "ACME"
        assert body["slug"] == "acme"
        assert body["plan"] == "free"
        assert body["active"] is True
        assert body["stats"]["n_users"] == 1

    def test_admin_creado_puede_login_y_es_company_admin(self, client):
        h = _superadmin_header(client)
        client.post("/api/admin/tenants", headers=h, json=self._payload())
        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@acme.com", "password": "password123"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["role"] == "company_admin"

    def test_slug_duplicado_409(self, client):
        h = _superadmin_header(client)
        client.post("/api/admin/tenants", headers=h, json=self._payload())
        # Mismo nombre → mismo slug
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(admin_email="admin2@acme.com"),
        )
        assert resp.status_code == 409

    def test_email_duplicado_409(self, client):
        h = _superadmin_header(client)
        client.post("/api/admin/tenants", headers=h, json=self._payload())
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(tenant_name="Otra Empresa"),
        )
        assert resp.status_code == 409

    def test_plan_invalido_422(self, client):
        h = _superadmin_header(client)
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(plan="premium"),
        )
        assert resp.status_code == 422

    def test_password_corta_422(self, client):
        h = _superadmin_header(client)
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(admin_password="corto"),
        )
        assert resp.status_code == 422

    def test_email_invalido_422(self, client):
        h = _superadmin_header(client)
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(admin_email="no-es-email"),
        )
        assert resp.status_code == 422

    def test_slug_tecnomedia_reservado_409(self, client):
        h = _superadmin_header(client)
        resp = client.post(
            "/api/admin/tenants",
            headers=h,
            json=self._payload(tenant_name="TecnoMedia"),
        )
        assert resp.status_code == 409

    def test_audit_log_registra_creacion(self, client):
        h = _superadmin_header(client)
        client.post("/api/admin/tenants", headers=h, json=self._payload())
        factory = client.app.state.test_db_factory
        with factory() as db:
            row = db.execute(
                select(AuditLog).where(AuditLog.action == "tenant.created")
            ).scalar_one()
            assert row.target_type == "tenant"
            import json

            payload = json.loads(row.payload_json)
            assert payload["name"] == "ACME"
            assert payload["admin_email"] == "admin@acme.com"


# --------------------------------------------------------------------
# Get
# --------------------------------------------------------------------


class TestAdminTenantsGet:
    def test_detail_incluye_users(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="DetailCo",
            user_email="d@d.com",
        )
        resp = client.get(f"/api/admin/tenants/{tid}", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "detailco"
        assert len(body["users"]) == 1
        assert body["users"][0]["email"] == "d@d.com"

    def test_404_si_no_existe(self, client):
        h = _superadmin_header(client)
        resp = client.get("/api/admin/tenants/9999", headers=h)
        assert resp.status_code == 404


# --------------------------------------------------------------------
# Patch
# --------------------------------------------------------------------


class TestAdminTenantsPatch:
    def test_actualiza_name(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="OldName",
            user_email="x@y.com",
        )
        resp = client.patch(
            f"/api/admin/tenants/{tid}", headers=h, json={"name": "New Name"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_suspender_bloquea_login_del_admin(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="WillSuspend",
            user_email="user@willsuspend.com",
        )
        # Login antes funciona
        login = client.post(
            "/api/auth/login",
            json={
                "email": "user@willsuspend.com",
                "password": "userpass123",
            },
        )
        assert login.status_code == 200
        # Suspender
        resp = client.patch(
            f"/api/admin/tenants/{tid}", headers=h, json={"active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False
        # Login después falla
        login2 = client.post(
            "/api/auth/login",
            json={
                "email": "user@willsuspend.com",
                "password": "userpass123",
            },
        )
        assert login2.status_code == 401

    def test_cambiar_plan(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="PlanCo",
            user_email="p@c.com",
        )
        resp = client.patch(
            f"/api/admin/tenants/{tid}", headers=h, json={"plan": "enterprise"}
        )
        assert resp.status_code == 200
        assert resp.json()["plan"] == "enterprise"

    def test_plan_invalido_422(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="X",
            user_email="x1@y.com",
        )
        resp = client.patch(
            f"/api/admin/tenants/{tid}", headers=h, json={"plan": "premium"}
        )
        assert resp.status_code == 422

    def test_no_se_puede_suspender_tecnomedia(self, client):
        h = _superadmin_header(client)
        # Buscar el id del tenant TecnoMedia
        factory = client.app.state.test_db_factory
        with factory() as db:
            tecno = db.execute(
                select(Tenant).where(Tenant.slug == "tecnomedia")
            ).scalar_one()
            tecno_id = tecno.id
        resp = client.patch(
            f"/api/admin/tenants/{tecno_id}",
            headers=h,
            json={"active": False},
        )
        assert resp.status_code == 409

    def test_404_si_no_existe(self, client):
        h = _superadmin_header(client)
        resp = client.patch("/api/admin/tenants/9999", headers=h, json={"name": "X"})
        assert resp.status_code == 404

    def test_audit_log_solo_si_hay_cambios(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="AuditCo",
            user_email="a@u.com",
            plan="free",
        )
        # PATCH con plan igual al actual → no audit
        client.patch(f"/api/admin/tenants/{tid}", headers=h, json={"plan": "free"})
        factory = client.app.state.test_db_factory
        with factory() as db:
            n = (
                db.execute(select(AuditLog).where(AuditLog.action == "tenant.updated"))
                .scalars()
                .all()
            )
            assert len(n) == 0
        # PATCH con cambio real → 1 audit
        client.patch(f"/api/admin/tenants/{tid}", headers=h, json={"plan": "basic"})
        with factory() as db:
            rows = (
                db.execute(select(AuditLog).where(AuditLog.action == "tenant.updated"))
                .scalars()
                .all()
            )
            assert len(rows) == 1


# --------------------------------------------------------------------
# Delete (hard cascade)
# --------------------------------------------------------------------


class TestAdminTenantsDelete:
    def test_borra_tenant_y_users(self, client):
        h = _superadmin_header(client)
        tid, uid = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="ToDelete",
            user_email="del@d.com",
        )
        resp = client.delete(f"/api/admin/tenants/{tid}", headers=h)
        assert resp.status_code == 204
        factory = client.app.state.test_db_factory
        with factory() as db:
            assert db.get(Tenant, tid) is None
            assert db.get(User, uid) is None

    def test_protege_tenant_tecnomedia(self, client):
        h = _superadmin_header(client)
        factory = client.app.state.test_db_factory
        with factory() as db:
            tecno = db.execute(
                select(Tenant).where(Tenant.slug == "tecnomedia")
            ).scalar_one()
            tecno_id = tecno.id
        resp = client.delete(f"/api/admin/tenants/{tecno_id}", headers=h)
        assert resp.status_code == 409

    def test_404_si_no_existe(self, client):
        h = _superadmin_header(client)
        resp = client.delete("/api/admin/tenants/9999", headers=h)
        assert resp.status_code == 404

    def test_rechaza_si_batch_running_409(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="HasRunning",
            user_email="r@r.com",
        )
        # Insertar batch en estado running
        from app.models.application import Application
        from app.models.batch import Batch

        factory = client.app.state.test_db_factory
        with factory() as db:
            app_row = Application(tenant_id=tid, name="App1", pipeline_json="[]")
            db.add(app_row)
            db.flush()
            db.add(
                Batch(
                    tenant_id=tid,
                    application_id=app_row.id,
                    state="running",
                )
            )
            db.commit()
        resp = client.delete(f"/api/admin/tenants/{tid}", headers=h)
        assert resp.status_code == 409

    def test_cascade_borra_applications_batches_pages(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="Casc",
            user_email="c@c.com",
        )
        from app.models.application import Application
        from app.models.batch import Batch
        from app.models.page import Page

        factory = client.app.state.test_db_factory
        with factory() as db:
            app_row = Application(tenant_id=tid, name="App1", pipeline_json="[]")
            db.add(app_row)
            db.flush()
            batch = Batch(
                tenant_id=tid,
                application_id=app_row.id,
                state="created",
            )
            db.add(batch)
            db.flush()
            db.add(
                Page(
                    batch_id=batch.id,
                    page_index=0,
                    image_path="some/path.png",
                )
            )
            db.commit()
            app_id = app_row.id
            batch_id = batch.id

        resp = client.delete(f"/api/admin/tenants/{tid}", headers=h)
        assert resp.status_code == 204

        with factory() as db:
            assert db.get(Application, app_id) is None
            assert db.get(Batch, batch_id) is None
            n_pages = db.execute(select(Page).where(Page.batch_id == batch_id)).first()
            assert n_pages is None

    def test_borra_archivos_de_storage(self, client, storage_dir):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="Files",
            user_email="f@f.com",
        )
        from app.models.application import Application
        from app.models.batch import Batch
        from app.models.page import Page

        factory = client.app.state.test_db_factory
        # Crear archivo real en el storage
        rel = f"{tid}/1/foo.png"
        target = storage_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"image data")
        assert target.exists()

        with factory() as db:
            app_row = Application(tenant_id=tid, name="App1", pipeline_json="[]")
            db.add(app_row)
            db.flush()
            batch = Batch(
                tenant_id=tid,
                application_id=app_row.id,
                state="created",
            )
            db.add(batch)
            db.flush()
            db.add(Page(batch_id=batch.id, page_index=0, image_path=rel))
            db.commit()

        resp = client.delete(f"/api/admin/tenants/{tid}", headers=h)
        assert resp.status_code == 204
        assert not target.exists()

    def test_audit_log_registra_borrado(self, client):
        h = _superadmin_header(client)
        tid, _ = _create_tenant_and_user(
            client.app.state.test_db_factory,
            tenant_name="AuditDel",
            user_email="ad@x.com",
        )
        client.delete(f"/api/admin/tenants/{tid}", headers=h)
        factory = client.app.state.test_db_factory
        with factory() as db:
            rows = (
                db.execute(select(AuditLog).where(AuditLog.action == "tenant.deleted"))
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].target_id == tid
            import json

            payload = json.loads(rows[0].payload_json)
            assert payload["slug"] == "auditdel"
