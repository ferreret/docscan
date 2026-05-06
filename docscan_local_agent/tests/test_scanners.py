"""Tests del endpoint GET /scanners.

Mockeamos ``scanner_factory`` con un FakeScanner para no depender de
SANE/TWAIN/WIA reales en CI. La integración con el backend real se
verifica en el smoke manual al final del hito.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import (
    get_scanner_factory,
    get_settings,
)
from docscan_local_agent.main import create_app
from docscan_local_agent.settings import AgentSettings


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeScanner:
    """BaseScanner mínimo para tests (no requiere SANE/TWAIN)."""

    def __init__(
        self,
        sources: list[str],
        backend: str = "sane",
        raise_on_list: Exception | None = None,
    ) -> None:
        self.sources = sources
        self._backend = backend
        self._raise = raise_on_list
        self.closed = False

    @property
    def backend_name(self) -> str:
        return self._backend

    def list_sources(self) -> list[str]:
        if self._raise is not None:
            raise self._raise
        return list(self.sources)

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Helpers
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


def _client_with_scanner(
    tmp_path: Path,
    scanner: FakeScanner | None,
    *,
    paired: bool = True,
    factory_raises: Exception | None = None,
) -> TestClient:
    """Crea TestClient con get_settings + get_scanner_factory overrideados."""
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings

    if paired:
        save_credentials(_sample_creds(), tmp_path)

    def _factory():
        if factory_raises is not None:
            raise factory_raises
        return scanner

    app.dependency_overrides[get_scanner_factory] = lambda: _factory
    return TestClient(app)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_scanners_returns_list(tmp_path: Path) -> None:
    """200 con backend + lista de scanners normalizados."""
    scanner = FakeScanner(
        sources=["epson:libusb:001:002", "fujitsu:fi-7160"],
        backend="sane",
    )
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners")
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "sane"
    assert body["scanners"] == [
        {"name": "epson:libusb:001:002", "backend": "sane"},
        {"name": "fujitsu:fi-7160", "backend": "sane"},
    ]


def test_scanners_returns_empty_list(tmp_path: Path) -> None:
    """Backend disponible pero sin dispositivos conectados → 200 + lista vacía."""
    scanner = FakeScanner(sources=[], backend="sane")
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners")
    assert resp.status_code == 200
    assert resp.json() == {"backend": "sane", "scanners": []}


def test_scanners_closes_scanner_on_success(tmp_path: Path) -> None:
    """Tras un list OK, scanner.close() se llama (libera recursos USB)."""
    scanner = FakeScanner(sources=["s1"])
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners")
    assert scanner.closed is True


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_scanners_unpaired_returns_401(tmp_path: Path) -> None:
    """Sin emparejar el agente NO debe ofrecer escáneres."""
    client = _client_with_scanner(tmp_path, FakeScanner(sources=["s1"]), paired=False)

    resp = client.get("/scanners")
    assert resp.status_code == 401


def test_scanners_unpaired_does_not_invoke_factory(tmp_path: Path) -> None:
    """El factory NO debe ejecutarse si la auth falla (no abre USB en vano)."""
    invoked: list[int] = []

    def _factory():
        invoked.append(1)
        return FakeScanner(sources=[])

    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_scanner_factory] = lambda: _factory
    client = TestClient(app)

    client.get("/scanners")
    assert invoked == []


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_scanners_no_backend_returns_503(tmp_path: Path) -> None:
    """Sistema sin backends de escáner instalados → 503 con mensaje claro."""
    client = _client_with_scanner(
        tmp_path,
        scanner=None,
        factory_raises=RuntimeError("No hay backends de escáner disponibles en Linux"),
    )

    resp = client.get("/scanners")
    assert resp.status_code == 503
    assert "backend" in resp.json()["detail"].lower()


def test_scanners_close_called_even_if_list_raises(tmp_path: Path) -> None:
    """Si list_sources lanza, igualmente cerramos el scanner."""
    scanner = FakeScanner(sources=[], raise_on_list=RuntimeError("usb gone"))
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners")
    assert resp.status_code == 500
    assert scanner.closed is True


def test_scanners_close_failure_does_not_mask_response(tmp_path: Path) -> None:
    """Si close() falla tras un list OK, el 200 se mantiene (close best-effort)."""

    class FlakyClose(FakeScanner):
        def close(self) -> None:  # type: ignore[override]
            super().close()
            raise OSError("close exploded")

    scanner = FlakyClose(sources=["s1"])
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["scanners"]) == 1
