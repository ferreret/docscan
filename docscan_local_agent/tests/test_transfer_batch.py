"""Tests del endpoint POST /transfer-batch del agente.

Hito 11 sprint cliente local web. El agente descarga el ZIP del lote
(reusando el endpoint /api/batches/{id}/export del SaaS, ampliado en
hito 11 para aceptar agent_token) y lo escribe en una ruta local del
PC del operario. Cubre el caso "servidor remoto sin acceso a la red
del cliente": el SaaS está en cloud y el resultado tiene que aterrizar
en un disco/red local del cliente.

Modos:
- ``extracted`` (default): extrae el ZIP en ``{destination}/batch_{id}/``.
- ``zip``: escribe el ZIP tal cual en ``{destination}/batch_{id}.zip``.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import (
    get_saas_client_factory,
    get_settings,
)
from docscan_local_agent.main import create_app
from docscan_local_agent.saas_client import SaasClient
from docscan_local_agent.settings import AgentSettings


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _sample_creds() -> AgentCredentials:
    return AgentCredentials(
        saas_url="https://saas.example.com",
        agent_token="7.deadbeef",
        device_id=7,
        device_name="Portátil Ana",
        user_email="ana@example.com",
        tenant_name="TecnoMedia",
        paired_at=datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


def _sample_zip(page_filenames: list[str], manifest_extra: dict | None = None) -> bytes:
    """Genera un ZIP con páginas (PNG mínimo) + manifest.json válido."""
    import json

    # PNG mínimo válido 1x1 negro
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00"
        b"\x00\x00\x00IEND\xaeB`\x82"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in page_filenames:
            zf.writestr(f"pages/{name}", png)
        manifest = {
            "batch_id": 42,
            "page_count": len(page_filenames),
            "pages": [
                {"page_index": i, "filename": f"pages/{n}"}
                for i, n in enumerate(page_filenames)
            ],
        }
        if manifest_extra:
            manifest.update(manifest_extra)
        zf.writestr("manifest.json", json.dumps(manifest))
    return buffer.getvalue()


def _client(
    tmp_path: Path,
    saas_handler,
    *,
    paired: bool = True,
) -> TestClient:
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    if paired:
        save_credentials(_sample_creds(), tmp_path)

    def _saas_factory(base_url: str) -> SaasClient:
        return SaasClient(
            base_url,
            http_client=httpx.Client(transport=httpx.MockTransport(saas_handler)),
        )

    app.dependency_overrides[get_saas_client_factory] = lambda: _saas_factory
    return TestClient(app)


def _saas_zip_handler(zip_bytes: bytes):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/export") and req.method == "GET":
            assert req.headers["authorization"] == "Bearer 7.deadbeef"
            return httpx.Response(
                200,
                content=zip_bytes,
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(404, json={"detail": "ruta inesperada"})

    return handler


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_transfer_batch_extracted_default(tmp_path: Path) -> None:
    """Mode default ('extracted'): ZIP se extrae en {destination}/batch_{id}/."""
    zip_bytes = _sample_zip(["page_0001.png", "page_0002.png"])
    destination = tmp_path / "out"
    client = _client(tmp_path / "config", _saas_zip_handler(zip_bytes))

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(destination)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    target_dir = destination / "batch_42"
    assert body["mode"] == "extracted"
    assert body["path"] == str(target_dir)
    assert body["files_count"] == 3  # 2 páginas + manifest.json
    assert (target_dir / "manifest.json").is_file()
    assert (target_dir / "pages" / "page_0001.png").is_file()
    assert (target_dir / "pages" / "page_0002.png").is_file()


def test_transfer_batch_mode_zip(tmp_path: Path) -> None:
    """Mode 'zip': escribe el ZIP tal cual en {destination}/batch_{id}.zip."""
    zip_bytes = _sample_zip(["page_0001.png"])
    destination = tmp_path / "out"
    client = _client(tmp_path / "config", _saas_zip_handler(zip_bytes))

    resp = client.post(
        "/transfer-batch",
        json={
            "batch_id": 42,
            "destination": str(destination),
            "mode": "zip",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    target = destination / "batch_42.zip"
    assert body["mode"] == "zip"
    assert body["path"] == str(target)
    assert target.is_file()
    assert target.read_bytes() == zip_bytes
    assert body["bytes"] == len(zip_bytes)


def test_transfer_batch_creates_destination_if_missing(tmp_path: Path) -> None:
    """Si destination no existe, mkdir -p."""
    zip_bytes = _sample_zip(["page_0001.png"])
    destination = tmp_path / "no" / "existe" / "todavia"
    client = _client(tmp_path / "config", _saas_zip_handler(zip_bytes))

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(destination)},
    )

    assert resp.status_code == 200
    assert destination.is_dir()
    assert (destination / "batch_42" / "manifest.json").is_file()


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_transfer_batch_unpaired_returns_401(tmp_path: Path) -> None:
    """Sin pairing: 401 antes de tocar el SaaS."""
    client = _client(tmp_path / "config", _saas_zip_handler(b""), paired=False)

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(tmp_path / "out")},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# validación del body
# ---------------------------------------------------------------------------


def test_transfer_batch_validation_missing_batch_id(tmp_path: Path) -> None:
    client = _client(tmp_path / "config", _saas_zip_handler(b""))

    resp = client.post(
        "/transfer-batch",
        json={"destination": str(tmp_path / "out")},
    )
    assert resp.status_code == 422


def test_transfer_batch_validation_empty_destination(tmp_path: Path) -> None:
    client = _client(tmp_path / "config", _saas_zip_handler(b""))

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": ""},
    )
    assert resp.status_code == 422


def test_transfer_batch_validation_invalid_mode(tmp_path: Path) -> None:
    client = _client(tmp_path / "config", _saas_zip_handler(b""))

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(tmp_path), "mode": "tarball"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# errores semánticos
# ---------------------------------------------------------------------------


def test_transfer_batch_destination_is_file_returns_400(tmp_path: Path) -> None:
    """Si destination apunta a un fichero existente, error 400 (no sobreescribir)."""
    file_destination = tmp_path / "soy_un_fichero.txt"
    file_destination.write_text("hola")
    client = _client(tmp_path / "config", _saas_zip_handler(b""))

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(file_destination)},
    )
    assert resp.status_code == 400
    assert "fichero" in resp.json()["detail"].lower()


def test_transfer_batch_saas_404_relayed(tmp_path: Path) -> None:
    """SaaS responde 404 (lote ajeno) → relayed con detail."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Lote no encontrado"})

    destination = tmp_path / "out"
    client = _client(tmp_path / "config", handler)

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 999, "destination": str(destination)},
    )
    assert resp.status_code == 404
    assert "lote" in resp.json()["detail"].lower()


def test_transfer_batch_saas_unavailable_returns_502(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    destination = tmp_path / "out"
    client = _client(tmp_path / "config", handler)

    resp = client.post(
        "/transfer-batch",
        json={"batch_id": 42, "destination": str(destination)},
    )
    assert resp.status_code == 502


def test_transfer_batch_corrupt_zip_returns_500(tmp_path: Path) -> None:
    """Si el SaaS devuelve algo que no es ZIP, el agente avisa con 500."""
    client = _client(tmp_path / "config", _saas_zip_handler(b"not a zip"))

    resp = client.post(
        "/transfer-batch",
        json={
            "batch_id": 42,
            "destination": str(tmp_path / "out"),
        },
    )
    assert resp.status_code == 500
    assert "zip" in resp.json()["detail"].lower()
