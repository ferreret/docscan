"""Tests del endpoint GET /status del agente local."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from docscan_local_agent import __version__
from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import get_settings
from docscan_local_agent.main import create_app
from docscan_local_agent.settings import AgentSettings


def _client_with_config_dir(tmp_path: Path) -> TestClient:
    """Crea TestClient con get_settings overrideado para usar tmp_path."""
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


# ---------------------------------------------------------------------------
# pre-pairing: paired=False
# ---------------------------------------------------------------------------


def test_status_returns_200(client: TestClient) -> None:
    """El endpoint /status responde 200 OK."""
    resp = client.get("/status")
    assert resp.status_code == 200


def test_status_returns_expected_payload(client: TestClient) -> None:
    """Sin agent.json el payload tiene paired=False y campos mínimos."""
    resp = client.get("/status")
    body = resp.json()
    assert body["name"] == "docscan-local-agent"
    assert body["version"] == __version__
    assert body["paired"] is False


def test_status_content_type_json(client: TestClient) -> None:
    """El content-type es JSON."""
    resp = client.get("/status")
    assert resp.headers["content-type"].startswith("application/json")


def test_status_pre_pairing_omits_paired_metadata(tmp_path: Path) -> None:
    """Sin credenciales no exponemos device_name/user_email/tenant_name."""
    client = _client_with_config_dir(tmp_path)
    body = client.get("/status").json()
    assert body["paired"] is False
    # Los campos de pairing son None u omitidos cuando no hay credenciales.
    assert body.get("device_name") is None
    assert body.get("user_email") is None
    assert body.get("tenant_name") is None


# ---------------------------------------------------------------------------
# post-pairing: paired=True con metadatos
# ---------------------------------------------------------------------------


def _sample_creds() -> AgentCredentials:
    return AgentCredentials(
        saas_url="https://saas.example.com",
        agent_token="7.deadbeef",
        device_id=7,
        device_name="Portátil Ana",
        user_email="ana@example.com",
        tenant_name="TecnoMedia",
        paired_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_status_with_credentials_returns_paired_true(tmp_path: Path) -> None:
    """Con agent.json válido en config_dir, paired=True + metadatos."""
    save_credentials(_sample_creds(), tmp_path)
    client = _client_with_config_dir(tmp_path)

    body = client.get("/status").json()
    assert body["paired"] is True
    assert body["device_name"] == "Portátil Ana"
    assert body["user_email"] == "ana@example.com"
    assert body["tenant_name"] == "TecnoMedia"


def test_status_never_exposes_agent_token(tmp_path: Path) -> None:
    """El agent_token nunca debe aparecer en /status (es secreto)."""
    save_credentials(_sample_creds(), tmp_path)
    client = _client_with_config_dir(tmp_path)

    body = client.get("/status").json()
    raw = client.get("/status").text
    assert "agent_token" not in body
    assert "deadbeef" not in raw  # ni el secret leakea


def test_status_corrupt_credentials_falls_back_to_unpaired(tmp_path: Path) -> None:
    """Un agent.json corrupto se trata como pre-pairing (no crashea)."""
    (tmp_path / "agent.json").write_text("{not json}")
    client = _client_with_config_dir(tmp_path)

    body = client.get("/status").json()
    assert body["paired"] is False
