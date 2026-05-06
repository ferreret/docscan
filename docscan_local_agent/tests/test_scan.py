"""Tests del endpoint POST /scan.

Generamos imágenes sintéticas con numpy y las pasamos por un FakeScanner
para no depender de un escáner físico durante los tests. La integración
con el backend real (SANE/TWAIN) la verificará el smoke manual.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.scanner_service import ScanConfig
from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import get_scanner_factory, get_settings
from docscan_local_agent.main import create_app
from docscan_local_agent.settings import AgentSettings


# ---------------------------------------------------------------------------
# FakeScanner que registra acquire() y devuelve una imagen sintética
# ---------------------------------------------------------------------------


def _synthetic_image(height: int = 100, width: int = 80) -> np.ndarray:
    """Genera un BGR aleatorio, suficiente para verificar PNG round-trip."""
    rng = np.random.default_rng(seed=42)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


class FakeScanner:
    def __init__(
        self,
        sources: list[str],
        backend: str = "sane",
        images_per_acquire: list[np.ndarray] | None = None,
        raise_on_acquire: Exception | None = None,
        return_empty: bool = False,
    ) -> None:
        self.sources = sources
        self._backend = backend
        self._images = images_per_acquire or [_synthetic_image()]
        self._raise = raise_on_acquire
        self._return_empty = return_empty
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
        if self._return_empty:
            return []
        return list(self._images)

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# helpers de test
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
    *,
    paired: bool = True,
    factory_raises: Exception | None = None,
) -> TestClient:
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


def _png_magic(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_scan_returns_png_bytes(tmp_path: Path) -> None:
    """200 con Content-Type image/png y bytes con la firma PNG válida."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner)

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert _png_magic(resp.content)
    # Decodificar de vuelta y comparar dimensiones contra la imagen sintética.
    arr = np.frombuffer(resp.content, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == (100, 80, 3)


def test_scan_passes_resolution_and_mode_to_scanner(tmp_path: Path) -> None:
    """El body llega al ScanConfig que ve el backend."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner)

    client.post(
        "/scan",
        json={"scanner_name": "dev:001", "resolution": 600, "mode": "Gray"},
    )

    assert len(scanner.acquire_calls) == 1
    source, config = scanner.acquire_calls[0]
    assert source == "dev:001"
    assert config.resolution == 600
    assert config.mode == "Gray"
    assert config.source_type == "flatbed"  # ADF se cubre en hito 8


def test_scan_uses_default_resolution_and_mode(tmp_path: Path) -> None:
    """Sin resolution/mode en el body usa 300 DPI y Color."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner)

    client.post("/scan", json={"scanner_name": "dev:001"})

    _, config = scanner.acquire_calls[0]
    assert config.resolution == 300
    assert config.mode == "Color"


def test_scan_returns_first_page_when_acquire_returns_multiple(
    tmp_path: Path,
) -> None:
    """En flatbed el backend debería devolver 1, pero si devuelve >1 tomamos la primera."""
    img1 = _synthetic_image(height=50, width=40)
    img2 = _synthetic_image(height=200, width=150)
    scanner = FakeScanner(sources=["dev:001"], images_per_acquire=[img1, img2])
    client = _client(tmp_path, scanner)

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    arr = np.frombuffer(resp.content, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert decoded.shape == (50, 40, 3)


def test_scan_closes_scanner_on_success(tmp_path: Path) -> None:
    """Tras un /scan OK, scanner.close() se llamó."""
    scanner = FakeScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner)

    client.post("/scan", json={"scanner_name": "dev:001"})

    assert scanner.closed is True


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_scan_unpaired_returns_401(tmp_path: Path) -> None:
    """Sin emparejar /scan responde 401 (defense in depth)."""
    client = _client(tmp_path, FakeScanner(sources=["dev:001"]), paired=False)

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    assert resp.status_code == 401


def test_scan_unpaired_does_not_invoke_factory(tmp_path: Path) -> None:
    """Sin pairing el factory ni se llama (no abre USB)."""
    invoked: list[int] = []

    def _factory():
        invoked.append(1)
        return FakeScanner(sources=["dev:001"])

    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_scanner_factory] = lambda: _factory
    client = TestClient(app)

    client.post("/scan", json={"scanner_name": "dev:001"})

    assert invoked == []


# ---------------------------------------------------------------------------
# validación
# ---------------------------------------------------------------------------


def test_scan_validation_missing_scanner_name(tmp_path: Path) -> None:
    """422 si no se pasa scanner_name."""
    client = _client(tmp_path, FakeScanner(sources=["dev:001"]))

    resp = client.post("/scan", json={})

    assert resp.status_code == 422


@pytest.mark.parametrize("bad_mode", ["Sepia", "color", ""])
def test_scan_validation_invalid_mode(tmp_path: Path, bad_mode: str) -> None:
    """Mode debe ser uno de los soportados (Color/Gray/Lineart)."""
    client = _client(tmp_path, FakeScanner(sources=["dev:001"]))

    resp = client.post("/scan", json={"scanner_name": "dev:001", "mode": bad_mode})

    assert resp.status_code == 422


@pytest.mark.parametrize("bad_resolution", [0, -1, 10000])
def test_scan_validation_invalid_resolution(
    tmp_path: Path, bad_resolution: int
) -> None:
    """Resolución fuera de rango razonable se rechaza con 422."""
    client = _client(tmp_path, FakeScanner(sources=["dev:001"]))

    resp = client.post(
        "/scan",
        json={"scanner_name": "dev:001", "resolution": bad_resolution},
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_scan_unknown_scanner_returns_404(tmp_path: Path) -> None:
    """Si scanner_name no aparece en list_sources, devolvemos 404."""
    scanner = FakeScanner(sources=["dev:001", "dev:002"])
    client = _client(tmp_path, scanner)

    resp = client.post("/scan", json={"scanner_name": "no:existe"})

    assert resp.status_code == 404
    detail = resp.json()["detail"].lower()
    assert "no:existe" in detail or "no existe" in detail
    # Y NO se llamó a acquire (sólo a list_sources).
    assert scanner.acquire_calls == []


def test_scan_no_backend_returns_503(tmp_path: Path) -> None:
    """Sin backend instalado el factory lanza RuntimeError → 503."""
    client = _client(
        tmp_path,
        scanner=None,
        factory_raises=RuntimeError("No hay backends de escáner"),
    )

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    assert resp.status_code == 503


def test_scan_acquire_raises_returns_500(tmp_path: Path) -> None:
    """Si acquire() falla, 500 con detalle y close() llamado."""
    scanner = FakeScanner(
        sources=["dev:001"],
        raise_on_acquire=RuntimeError("paper jam"),
    )
    client = _client(tmp_path, scanner)

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    assert resp.status_code == 500
    assert "paper jam" in resp.json()["detail"].lower()
    assert scanner.closed is True


def test_scan_empty_acquire_returns_500(tmp_path: Path) -> None:
    """acquire() devuelve lista vacía → 500 con detalle (no 200 sin imagen)."""
    scanner = FakeScanner(sources=["dev:001"], return_empty=True)
    client = _client(tmp_path, scanner)

    resp = client.post("/scan", json={"scanner_name": "dev:001"})

    assert resp.status_code == 500
    assert "no devolvi" in resp.json()["detail"].lower()
    assert scanner.closed is True
