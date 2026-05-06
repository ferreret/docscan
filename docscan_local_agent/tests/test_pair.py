"""Tests del endpoint POST /pair del agente local.

Mockeamos el SaaS con ``httpx.MockTransport`` y el ``config_dir`` con
``tmp_path`` para no tocar HOME real ni la red.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from docscan_local_agent.credentials import load_credentials
from docscan_local_agent.deps import get_saas_client_factory, get_settings
from docscan_local_agent.main import create_app
from docscan_local_agent.saas_client import SaasClient
from docscan_local_agent.settings import AgentSettings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _whoami_payload() -> dict:
    return {
        "device_id": 7,
        "name": "Portátil Ana",
        "user": {
            "id": 3,
            "email": "ana@example.com",
            "display_name": "Ana García",
            "role": "operator",
        },
        "tenant": {"id": 2, "name": "TecnoMedia", "slug": "tecnomedia"},
        "paired_at": "2026-05-06T12:00:00",
        "last_seen": None,
    }


def _saas_handler_happy() -> "callable":
    """Handler que simula un SaaS contento (claim 200 + whoami 200)."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/agent/pair-claim":
            return httpx.Response(
                200, json={"agent_token": "7.deadbeef", "device_id": 7}
            )
        if req.url.path == "/api/agent/whoami":
            assert req.headers["authorization"] == "Bearer 7.deadbeef"
            return httpx.Response(200, json=_whoami_payload())
        return httpx.Response(404)

    return handler


def _make_app(tmp_path: Path, handler) -> TestClient:
    """Crea la app con DI overrideado para usar tmp_path + handler mock."""
    app = create_app()

    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings

    def _factory(base_url: str) -> SaasClient:
        return SaasClient(
            base_url, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    app.dependency_overrides[get_saas_client_factory] = lambda: _factory
    return TestClient(app)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_pair_success_returns_summary_without_token(tmp_path: Path) -> None:
    """200, response sin agent_token, paired=true, datos del whoami."""
    client = _make_app(tmp_path, _saas_handler_happy())

    resp = client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "ABCD2345"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["paired"] is True
    assert body["device_id"] == 7
    assert body["device_name"] == "Portátil Ana"
    assert body["user_email"] == "ana@example.com"
    assert body["tenant_name"] == "TecnoMedia"
    assert "agent_token" not in body  # nunca se filtra al frontend


def test_pair_persists_credentials_to_disk(tmp_path: Path) -> None:
    """Tras un /pair OK, agent.json contiene todas las credenciales."""
    client = _make_app(tmp_path, _saas_handler_happy())

    resp = client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "ABCD2345"},
    )
    assert resp.status_code == 200

    creds = load_credentials(tmp_path)
    assert creds is not None
    assert creds.saas_url == "https://saas.example.com"
    assert creds.agent_token == "7.deadbeef"
    assert creds.device_id == 7
    assert creds.device_name == "Portátil Ana"
    assert creds.user_email == "ana@example.com"
    assert creds.tenant_name == "TecnoMedia"


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_pair_when_already_paired_returns_409(tmp_path: Path) -> None:
    """Re-pairing en un agente ya emparejado responde 409 sin tocar el SaaS."""
    # Pre-pairing: dejamos credenciales en disco.
    client = _make_app(tmp_path, _saas_handler_happy())
    client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "ABCD2345"},
    )

    # Segundo intento debe fallar antes de llamar al SaaS.
    saas_called = []

    def handler(req: httpx.Request) -> httpx.Response:
        saas_called.append(req.url.path)
        return httpx.Response(500)

    client2 = _make_app(tmp_path, handler)
    resp = client2.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "OTRO1234"},
    )

    assert resp.status_code == 409
    assert "ya" in resp.json()["detail"].lower()
    assert saas_called == []  # ni un solo HTTP al SaaS


def test_pair_invalid_code_relays_404(tmp_path: Path) -> None:
    """SaaS responde 404 → agente devuelve 404 con el mismo detail."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Código de pairing no válido"})

    client = _make_app(tmp_path, handler)
    resp = client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "WRONGCD2"},
    )

    assert resp.status_code == 404
    assert "no válido" in resp.json()["detail"].lower()


def test_pair_expired_code_relays_410(tmp_path: Path) -> None:
    """SaaS responde 410 → agente devuelve 410 con el mismo detail."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(410, json={"detail": "Código de pairing expirado"})

    client = _make_app(tmp_path, handler)
    resp = client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "ABCD2345"},
    )

    assert resp.status_code == 410
    assert "expirado" in resp.json()["detail"].lower()


def test_pair_saas_unavailable_returns_502(tmp_path: Path) -> None:
    """Si la red al SaaS falla, devolvemos 502 Bad Gateway."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _make_app(tmp_path, handler)
    resp = client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "ABCD2345"},
    )

    assert resp.status_code == 502
    assert "saas" in resp.json()["detail"].lower()


def test_pair_failure_does_not_persist_credentials(tmp_path: Path) -> None:
    """Tras un fallo de pair, agent.json NO existe."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Código no válido"})

    client = _make_app(tmp_path, handler)
    client.post(
        "/pair",
        json={"saas_url": "https://saas.example.com", "code": "WRONGCD2"},
    )

    assert load_credentials(tmp_path) is None
    assert not (tmp_path / "agent.json").exists()


def test_pair_validation_missing_code_returns_422(tmp_path: Path) -> None:
    """Sin ``code`` en el body, FastAPI valida y devuelve 422."""
    client = _make_app(tmp_path, _saas_handler_happy())
    resp = client.post("/pair", json={"saas_url": "https://saas.example.com"})
    assert resp.status_code == 422


def test_pair_validation_empty_code_returns_422(tmp_path: Path) -> None:
    """Code vacío también se rechaza con 422."""
    client = _make_app(tmp_path, _saas_handler_happy())
    resp = client.post(
        "/pair", json={"saas_url": "https://saas.example.com", "code": ""}
    )
    assert resp.status_code == 422
