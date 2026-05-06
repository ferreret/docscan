"""Tests de la dependency ``require_paired``.

Esta dependency protege los endpoints que sólo tienen sentido cuando el
agente ya está vinculado a un user/tenant del SaaS (escaneo, subida).

- 401 si no hay ``agent.json`` válido en el ``config_dir``.
- 200 + credentials inyectadas en el handler si lo hay.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import get_settings, require_paired
from docscan_local_agent.settings import AgentSettings


def _build_test_app(tmp_path: Path) -> FastAPI:
    """App mínima con un endpoint protegido para ejercitar require_paired."""
    app = FastAPI()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings

    router = APIRouter()

    @router.get("/protegido")
    def handler(creds: AgentCredentials = Depends(require_paired)) -> dict:
        return {"tenant": creds.tenant_name, "device_id": creds.device_id}

    app.include_router(router)
    return app


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


def test_require_paired_blocks_when_unpaired(tmp_path: Path) -> None:
    """Sin agent.json el handler nunca se ejecuta y la respuesta es 401."""
    client = TestClient(_build_test_app(tmp_path))

    resp = client.get("/protegido")
    assert resp.status_code == 401
    assert "empareja" in resp.json()["detail"].lower()


def test_require_paired_passes_credentials_when_paired(tmp_path: Path) -> None:
    """Con agent.json válido, el handler recibe las credenciales como param."""
    save_credentials(_sample_creds(), tmp_path)
    client = TestClient(_build_test_app(tmp_path))

    resp = client.get("/protegido")
    assert resp.status_code == 200
    assert resp.json() == {"tenant": "TecnoMedia", "device_id": 7}


def test_require_paired_treats_corrupt_credentials_as_unpaired(
    tmp_path: Path,
) -> None:
    """agent.json corrupto se trata como pre-pairing (401), no 500."""
    (tmp_path / "agent.json").write_text("{not json}")
    client = TestClient(_build_test_app(tmp_path))

    resp = client.get("/protegido")
    assert resp.status_code == 401
