"""Tests del router /api/agent/* (Hito 3 sprint cliente local web).

Cubre los 4 endpoints (pair-init, pair-claim, whoami, heartbeat) con
casos felices y errores: token inválido, código expirado, código ya
consumido, mezcla JWT user / agent_token, etc.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
import web.api._register_models  # noqa: F401  registra todas las tablas

import web.api.database as _db_module
from web.api.auth.dependencies import CurrentUserOrAgent
from web.api.auth.security import hash_password
from web.api.database import get_db
from web.api.main import create_app
from web.api.models import AgentDevice, ROLE_OPERATOR, Tenant, User
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
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _create_user_and_login(
    client: TestClient,
    *,
    email: str = "ana@acme.com",
    password: str = "Pass1234!",
    tenant_name: str = "Acme",
    role: str = ROLE_OPERATOR,
) -> tuple[int, str]:
    """Crea tenant+user en BD y devuelve (user_id, jwt_token)."""
    factory = client.app.state.test_db_factory
    with factory() as db:
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).one_or_none()
        if tenant is None:
            tenant = Tenant(name=tenant_name, slug=tenant_name.lower())
            db.add(tenant)
            db.flush()
        user = User(
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password(password),
            display_name=email.split("@")[0],
            role=role,
        )
        db.add(user)
        db.commit()
        user_id = user.id

    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return user_id, resp.json()["access_token"]


def _user_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _agent_header(agent_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {agent_token}"}


# --------------------------------------------------------------------
# POST /api/agent/pair-init
# --------------------------------------------------------------------


class TestPairInit:
    def test_pair_init_genera_codigo(self, client):
        _, token = _create_user_and_login(client)
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil Ana"},
            headers=_user_header(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "code" in body
        assert len(body["code"]) == 8
        assert body["device_id"] > 0
        assert "expires_at" in body

    def test_pair_init_requiere_user_jwt(self, client):
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "huérfano"},
        )
        assert resp.status_code == 401

    def test_pair_init_persiste_device_pre_pairing(self, client):
        _, token = _create_user_and_login(client)
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "estación-1"},
            headers=_user_header(token),
        )
        device_id = resp.json()["device_id"]
        factory = client.app.state.test_db_factory
        with factory() as db:
            device = db.get(AgentDevice, device_id)
            assert device is not None
            assert device.name == "estación-1"
            assert device.pairing_code is not None
            assert len(device.pairing_code) == 8
            assert device.token_hash is None
            assert device.paired_at is None


# --------------------------------------------------------------------
# POST /api/agent/pair-claim
# --------------------------------------------------------------------


class TestPairClaim:
    def test_pair_claim_codigo_invalido_404(self, client):
        resp = client.post(
            "/api/agent/pair-claim",
            json={"code": "NOEXISTE"},
        )
        assert resp.status_code == 404

    def test_pair_claim_codigo_expirado_410(self, client):
        _, token = _create_user_and_login(client)
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "d"},
            headers=_user_header(token),
        )
        device_id = resp.json()["device_id"]
        code = resp.json()["code"]

        # Forzar expiración manipulando la BD.
        factory = client.app.state.test_db_factory
        with factory() as db:
            device = db.get(AgentDevice, device_id)
            device.code_expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.commit()

        resp = client.post("/api/agent/pair-claim", json={"code": code})
        assert resp.status_code == 410

    def test_pair_claim_doble_uso_404(self, client):
        """Tras un claim exitoso, el código se nullea — segundo claim → 404."""
        _, token = _create_user_and_login(client)
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "d"},
            headers=_user_header(token),
        )
        code = resp.json()["code"]

        # Primer claim OK.
        r1 = client.post("/api/agent/pair-claim", json={"code": code})
        assert r1.status_code == 200

        # Segundo claim → 404 (pairing_code ya nullificado).
        r2 = client.post("/api/agent/pair-claim", json={"code": code})
        assert r2.status_code == 404

    def test_pair_claim_exitoso_devuelve_token(self, client):
        _, token = _create_user_and_login(client)
        resp = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(token),
        )
        code = resp.json()["code"]
        device_id = resp.json()["device_id"]

        resp = client.post("/api/agent/pair-claim", json={"code": code})
        assert resp.status_code == 200
        body = resp.json()
        # El token tiene formato {device_id}.{secret_hex}
        assert body["device_id"] == device_id
        assert body["agent_token"].startswith(f"{device_id}.")
        # 64 chars hex tras el punto.
        secret_part = body["agent_token"].split(".", 1)[1]
        assert len(secret_part) == 64

        # El device en BD ya no tiene pairing_code y sí tiene token_hash.
        factory = client.app.state.test_db_factory
        with factory() as db:
            d = db.get(AgentDevice, device_id)
            assert d.pairing_code is None
            assert d.token_hash is not None
            assert d.paired_at is not None


# --------------------------------------------------------------------
# GET /api/agent/whoami
# --------------------------------------------------------------------


class TestWhoami:
    def _pair_full(self, client) -> tuple[int, str]:
        """Helper: pair completo, devuelve (device_id, agent_token)."""
        _, token = _create_user_and_login(client)
        r = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(token),
        )
        code = r.json()["code"]
        r2 = client.post("/api/agent/pair-claim", json={"code": code})
        return r2.json()["device_id"], r2.json()["agent_token"]

    def test_whoami_sin_token_401(self, client):
        resp = client.get("/api/agent/whoami")
        assert resp.status_code == 401

    def test_whoami_con_jwt_user_no_vale(self, client):
        """Un JWT de usuario NO debe pasar como agent_token."""
        _, jwt_token = _create_user_and_login(client)
        resp = client.get("/api/agent/whoami", headers=_user_header(jwt_token))
        # JWT no tiene formato {id}.{secret} → 401.
        assert resp.status_code == 401

    def test_whoami_con_token_invalido_401(self, client):
        resp = client.get(
            "/api/agent/whoami",
            headers=_agent_header("99999.deadbeef"),
        )
        assert resp.status_code == 401

    def test_whoami_devuelve_info_completa(self, client):
        device_id, agent_token = self._pair_full(client)
        resp = client.get("/api/agent/whoami", headers=_agent_header(agent_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["device_id"] == device_id
        assert body["name"] == "Portátil"
        assert body["user"]["email"] == "ana@acme.com"
        assert body["tenant"]["name"] == "Acme"
        assert body["tenant"]["slug"] == "acme"
        assert body["paired_at"] is not None


# --------------------------------------------------------------------
# POST /api/agent/heartbeat
# --------------------------------------------------------------------


class TestHeartbeat:
    def _pair_full(self, client) -> tuple[int, str]:
        _, token = _create_user_and_login(client)
        r = client.post(
            "/api/agent/pair-init",
            json={"name": "d"},
            headers=_user_header(token),
        )
        code = r.json()["code"]
        r2 = client.post("/api/agent/pair-claim", json={"code": code})
        return r2.json()["device_id"], r2.json()["agent_token"]

    def test_heartbeat_actualiza_last_seen(self, client):
        device_id, agent_token = self._pair_full(client)

        # Antes: last_seen es NULL.
        factory = client.app.state.test_db_factory
        with factory() as db:
            assert db.get(AgentDevice, device_id).last_seen is None

        resp = client.post("/api/agent/heartbeat", headers=_agent_header(agent_token))
        assert resp.status_code == 200
        assert "last_seen" in resp.json()

        # Después: last_seen está fijado.
        with factory() as db:
            assert db.get(AgentDevice, device_id).last_seen is not None

    def test_heartbeat_sin_token_401(self, client):
        resp = client.post("/api/agent/heartbeat")
        assert resp.status_code == 401

    def test_heartbeat_con_token_invalido_401(self, client):
        resp = client.post(
            "/api/agent/heartbeat",
            headers=_agent_header("1.cafe1234"),
        )
        assert resp.status_code == 401


# --------------------------------------------------------------------
# Dependency híbrida user-or-agent (Hito 7)
# --------------------------------------------------------------------


@pytest.fixture
def hybrid_client(_test_engine, storage_dir):
    """Variante del fixture ``client`` que monta GET /_test_principal.

    El endpoint se añade ANTES de instanciar TestClient para que FastAPI
    lo procese en el startup (rutas añadidas post-startup quedan con
    schema parseado a medias y devuelven 422 en vez de 401).
    """
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

    @app.get("/_test_principal")
    def _ep(p: CurrentUserOrAgent) -> dict:  # type: ignore[valid-type]
        return {
            "tenant_id": p.tenant_id,
            "user_id": p.user_id,
            "is_agent": p.is_agent,
            "agent_device_id": p.agent_device_id,
        }

    with TestClient(app) as c:
        yield c


class TestHybridAuth:
    """Tests directos de get_current_user_or_agent.

    Usa ``hybrid_client`` que tiene el endpoint dummy ``/_test_principal``
    montado para ejercitar la dependency sin acoplarla a upload_pages
    (que se cubre en TestUploadPagesAgent).
    """

    def test_jwt_user_passes_and_marks_is_agent_false(self, hybrid_client):
        user_id, jwt_token = _create_user_and_login(hybrid_client)

        resp = hybrid_client.get("/_test_principal", headers=_user_header(jwt_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user_id
        assert body["is_agent"] is False
        assert body["agent_device_id"] is None

    def test_agent_token_passes_and_marks_is_agent_true(self, hybrid_client):
        # Pair full: crea user + device + obtiene agent_token.
        user_id, jwt_token = _create_user_and_login(hybrid_client)
        r = hybrid_client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        device_id = r.json()["device_id"]
        agent_token = hybrid_client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        resp = hybrid_client.get("/_test_principal", headers=_agent_header(agent_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user_id  # el user dueño del device
        assert body["is_agent"] is True
        assert body["agent_device_id"] == device_id

    def test_no_auth_returns_401(self, hybrid_client):
        resp = hybrid_client.get("/_test_principal")
        assert resp.status_code == 401

    def test_non_bearer_returns_401(self, hybrid_client):
        resp = hybrid_client.get(
            "/_test_principal", headers={"Authorization": "Basic abc"}
        )
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self, hybrid_client):
        resp = hybrid_client.get(
            "/_test_principal",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_invalid_jwt_does_not_fall_through_to_agent(self, hybrid_client):
        """Un JWT malformado NO debe pasar como agent_token aunque tenga punto."""
        resp = hybrid_client.get(
            "/_test_principal",
            headers={"Authorization": "Bearer aaa.bbb"},
        )
        assert resp.status_code == 401

    def test_agent_token_for_inactive_device_returns_401(self, hybrid_client):
        _, jwt_token = _create_user_and_login(hybrid_client)
        r = hybrid_client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        device_id = r.json()["device_id"]
        agent_token = hybrid_client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        # Desactivar el device en BD.
        factory = hybrid_client.app.state.test_db_factory
        with factory() as db:
            d = db.get(AgentDevice, device_id)
            d.active = False
            db.commit()

        resp = hybrid_client.get("/_test_principal", headers=_agent_header(agent_token))
        assert resp.status_code == 401

    def test_agent_token_with_suspended_tenant_returns_401(self, hybrid_client):
        _, jwt_token = _create_user_and_login(hybrid_client)
        r = hybrid_client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        agent_token = hybrid_client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        # Suspender el tenant del user.
        factory = hybrid_client.app.state.test_db_factory
        with factory() as db:
            tenant = db.query(Tenant).filter(Tenant.name == "Acme").one()
            tenant.active = False
            db.commit()

        resp = hybrid_client.get("/_test_principal", headers=_agent_header(agent_token))
        assert resp.status_code == 401

    def test_jwt_user_with_suspended_tenant_returns_401(self, hybrid_client):
        _, jwt_token = _create_user_and_login(hybrid_client)

        factory = hybrid_client.app.state.test_db_factory
        with factory() as db:
            tenant = db.query(Tenant).filter(Tenant.name == "Acme").one()
            tenant.active = False
            db.commit()

        resp = hybrid_client.get("/_test_principal", headers=_user_header(jwt_token))
        assert resp.status_code == 401


# --------------------------------------------------------------------
# Upload pages con agent_token (Hito 7B)
# --------------------------------------------------------------------


class TestUploadPagesAgent:
    """Tests del endpoint POST /api/batches/:id/pages aceptando agent_token.

    Cubre:
      - JWT user sigue funcionando (regresión)
      - agent_token sube página OK al lote del propio tenant
      - agent_token NO ve / NO puede subir al lote de otro tenant (404)
      - agent_token con device inactivo → 401
    """

    def _pair_full(self, client) -> tuple[int, str, int]:
        """Pair completo. Devuelve (user_id, agent_token, tenant_id)."""
        user_id, jwt_token = _create_user_and_login(client)
        r = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil Ana"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        agent_token = client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        # Sacar el tenant_id del user.
        factory = client.app.state.test_db_factory
        with factory() as db:
            user = db.get(User, user_id)
            tenant_id = user.tenant_id
        return user_id, agent_token, tenant_id

    def _create_application(self, client, headers: dict[str, str]) -> int:
        """Crea una aplicación bajo el tenant del header dado."""
        resp = client.post(
            "/api/applications",
            headers=headers,
            json={"name": "App", "description": ""},
        )
        assert resp.status_code in (200, 201), resp.text
        return resp.json()["id"]

    def _create_batch(self, client, jwt_token: str) -> int:
        """Crea un batch con JWT user (única vía). Devuelve batch_id."""
        h = _user_header(jwt_token)
        app_id = self._create_application(client, h)
        resp = client.post(
            "/api/batches",
            headers=h,
            json={"name": "Lote", "application_id": app_id},
        )
        assert resp.status_code in (200, 201), resp.text
        return resp.json()["id"]

    @staticmethod
    def _png_bytes() -> bytes:
        """PNG mínimo válido (1x1 negro)."""
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (1, 1), (0, 0, 0)).save(buf, format="PNG")
        return buf.getvalue()

    def test_jwt_user_can_still_upload(self, client):
        """Regresión: el flujo histórico con JWT user sigue funcionando."""
        _, jwt_token = _create_user_and_login(client)
        batch_id = self._create_batch(client, jwt_token)

        files = [("files", ("a.png", self._png_bytes(), "image/png"))]
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=_user_header(jwt_token),
            files=files,
        )
        assert resp.status_code == 201
        assert resp.json()["batch_page_count"] == 1

    def test_agent_token_uploads_page_to_own_tenant(self, client):
        """Un agent_token de tenant T puede subir páginas al lote de T."""
        _, jwt_token = _create_user_and_login(client)
        batch_id = self._create_batch(client, jwt_token)

        # Pair: el agente queda asociado al mismo user/tenant.
        r = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        agent_token = client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        files = [("files", ("scan.png", self._png_bytes(), "image/png"))]
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=_agent_header(agent_token),
            files=files,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["batch_page_count"] == 1
        assert resp.json()["created"][0]["batch_id"] == batch_id

    def test_agent_token_cannot_upload_to_other_tenant_batch(self, client):
        """Aislamiento multi-tenant: agent de TenantA contra batch de TenantB → 404."""
        # TenantA con su agent_token.
        _, agent_token_a, _ = self._pair_full(client)

        # TenantB con su batch.
        _, jwt_b = _create_user_and_login(
            client,
            email="bob@bcorp.com",
            password="Pass1234!",
            tenant_name="BCorp",
        )
        batch_b = self._create_batch(client, jwt_b)

        # Intento: agent_token_A sube al batch de TenantB.
        files = [("files", ("x.png", self._png_bytes(), "image/png"))]
        resp = client.post(
            f"/api/batches/{batch_b}/pages",
            headers=_agent_header(agent_token_a),
            files=files,
        )
        # 404 (sin distinguir "no existe" de "no es tuyo" — política del SaaS).
        assert resp.status_code == 404

    def test_agent_token_inactive_device_returns_401(self, client):
        """Si el device se desactiva, el agent_token deja de valer."""
        user_id, jwt_token = _create_user_and_login(client)
        batch_id = self._create_batch(client, jwt_token)

        r = client.post(
            "/api/agent/pair-init",
            json={"name": "Portátil"},
            headers=_user_header(jwt_token),
        )
        code = r.json()["code"]
        device_id = r.json()["device_id"]
        agent_token = client.post(
            "/api/agent/pair-claim", json={"code": code}
        ).json()["agent_token"]

        factory = client.app.state.test_db_factory
        with factory() as db:
            d = db.get(AgentDevice, device_id)
            d.active = False
            db.commit()

        files = [("files", ("x.png", self._png_bytes(), "image/png"))]
        resp = client.post(
            f"/api/batches/{batch_id}/pages",
            headers=_agent_header(agent_token),
            files=files,
        )
        assert resp.status_code == 401
