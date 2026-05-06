"""Tests del endpoint POST /scan-and-upload del agente.

Combina /scan + upload al SaaS en una sola operación. El frontend lo
usa para que el navegador no tenga que recibir el PNG y reenviarlo
(doble salto evitable).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
from fastapi.testclient import TestClient

from app.services.scanner_service import ScanConfig
from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import (
    get_saas_client_factory,
    get_scanner_factory,
    get_settings,
)
from docscan_local_agent.main import create_app
from docscan_local_agent.saas_client import SaasClient
from docscan_local_agent.settings import AgentSettings


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


def _synthetic_image() -> np.ndarray:
    rng = np.random.default_rng(seed=7)
    return rng.integers(0, 256, size=(50, 40, 3), dtype=np.uint8)


class FakeScanner:
    def __init__(
        self,
        sources: list[str],
        backend: str = "sane",
        images_per_acquire: list[np.ndarray] | None = None,
        raise_on_acquire: Exception | None = None,
    ) -> None:
        self.sources = sources
        self._backend = backend
        self._images = images_per_acquire or [_synthetic_image()]
        self._raise = raise_on_acquire
        self.closed = False
        self.acquire_calls: list[tuple[str, ScanConfig]] = []

    @property
    def backend_name(self) -> str:
        return self._backend

    def list_sources(self) -> list[str]:
        return list(self.sources)

    def acquire(self, source: str, config: ScanConfig) -> list[np.ndarray]:
        self.acquire_calls.append((source, config))
        if self._raise is not None:
            raise self._raise
        return list(self._images)

    def close(self) -> None:
        self.closed = True


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
        paired_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def _client(
    tmp_path: Path,
    scanner: FakeScanner | None,
    saas_handler,
    *,
    paired: bool = True,
) -> TestClient:
    """Crea TestClient con get_settings, scanner_factory y saas_factory mockeados."""
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    if paired:
        save_credentials(_sample_creds(), tmp_path)

    def _scanner_factory():
        return scanner

    def _saas_factory(base_url: str) -> SaasClient:
        return SaasClient(
            base_url,
            http_client=httpx.Client(transport=httpx.MockTransport(saas_handler)),
        )

    app.dependency_overrides[get_scanner_factory] = lambda: _scanner_factory
    app.dependency_overrides[get_saas_client_factory] = lambda: _saas_factory
    return TestClient(app)


def _saas_happy_handler():
    """SaaS que acepta upload con 201 + payload típico."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/pages") and req.method == "POST":
            assert req.headers["authorization"] == "Bearer 7.deadbeef"
            return httpx.Response(
                201,
                json={
                    "created": [
                        {
                            "id": 100,
                            "batch_id": 42,
                            "page_index": 0,
                            "image_path": "1/42/abc.png",
                            "is_excluded": False,
                            "review_reason": None,
                            "fields": {},
                            "flags": {},
                        }
                    ],
                    "batch_page_count": 1,
                },
            )
        return httpx.Response(404, json={"detail": "ruta inesperada"})

    return handler


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_scan_and_upload_happy(tmp_path: Path) -> None:
    """Captura + upload OK → 201 con la respuesta del SaaS."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["batch_page_count"] == 1
    assert body["created"][0]["batch_id"] == 42
    assert body["created"][0]["page_index"] == 0
    # No debe filtrar el agent_token.
    assert "agent_token" not in resp.text


def test_scan_and_upload_calls_acquire_with_config(tmp_path: Path) -> None:
    """Los params del body llegan al ScanConfig."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    client.post(
        "/scan-and-upload",
        json={
            "scanner_name": "dev:001",
            "batch_id": 42,
            "resolution": 600,
            "mode": "Gray",
        },
    )

    assert len(scanner.acquire_calls) == 1
    source, config = scanner.acquire_calls[0]
    assert source == "dev:001"
    assert config.resolution == 600
    assert config.mode == "Gray"
    assert config.source_type == "flatbed"


def test_scan_and_upload_closes_scanner_on_success(tmp_path: Path) -> None:
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert scanner.closed is True


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_scan_and_upload_unpaired_returns_401(tmp_path: Path) -> None:
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler(), paired=False)

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# validación
# ---------------------------------------------------------------------------


def test_scan_and_upload_validation_missing_batch_id(tmp_path: Path) -> None:
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    resp = client.post("/scan-and-upload", json={"scanner_name": "dev:001"})
    assert resp.status_code == 422


def test_scan_and_upload_validation_missing_scanner_name(tmp_path: Path) -> None:
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    resp = client.post("/scan-and-upload", json={"batch_id": 42})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_scan_and_upload_unknown_scanner_returns_404(tmp_path: Path) -> None:
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_happy_handler())

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "no:existe", "batch_id": 42},
    )
    assert resp.status_code == 404
    assert scanner.acquire_calls == []  # ni se intenta capturar


def test_scan_and_upload_saas_404_relayed(tmp_path: Path) -> None:
    """SaaS responde 404 (batch ajeno) → relayed con detail."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Lote no encontrado"})

    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, handler)

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 999},
    )
    assert resp.status_code == 404
    assert "lote" in resp.json()["detail"].lower()


def test_scan_and_upload_saas_401_relayed(tmp_path: Path) -> None:
    """SaaS responde 401 (token revocado) → relayed."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Agente no encontrado"})

    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, handler)

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 401


def test_scan_and_upload_saas_unavailable_returns_502(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, handler)

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 502


def test_scan_and_upload_acquire_raises_returns_500(tmp_path: Path) -> None:
    scanner = FakeScanner(
        sources=["dev:001"],
        raise_on_acquire=RuntimeError("paper jam"),
    )
    client = _client(tmp_path, scanner, _saas_happy_handler())

    resp = client.post(
        "/scan-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 500
    assert scanner.closed is True
