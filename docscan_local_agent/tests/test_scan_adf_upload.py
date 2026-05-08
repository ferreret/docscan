"""Tests del endpoint POST /scan-adf-and-upload del agente.

Hito 8 sprint cliente local web: el agente captura todo el ADF y sube
página a página al SaaS, emitiendo NDJSON con un evento por página
para que el frontend muestre progreso en tiempo real (en vez de esperar
varios minutos a un único 201 con N páginas).

El stream tiene 4 tipos de evento:
- ``started``: una sola línea al abrir.
- ``page_uploaded``: una por página subida con éxito (page_index, page_id).
- ``completed``: una sola línea al final con el total.
- ``error``: si algo se rompe a mitad de iteración. Tras error el stream se cierra.

El endpoint NO chequea ``is_disconnected``: si el cliente cierra a media
cinta, el bucle agota el ADF y las páginas siguen subiendo al SaaS. Es
deliberado — perder páginas ya capturadas sería peor UX que un cliente
que no ve los últimos eventos.
"""

from __future__ import annotations

import json
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


def _synthetic_image(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed=seed)
    return rng.integers(0, 256, size=(50, 40, 3), dtype=np.uint8)


class FakeAdfScanner:
    """Scanner con ``acquire_iter`` real para el bucle ADF.

    A diferencia del FakeScanner del test single-page, aquí los tests
    sí tocan la ruta de streaming, así que el método relevante es el
    generator.
    """

    def __init__(
        self,
        sources: list[str],
        pages: list[np.ndarray] | None = None,
        raise_at_index: tuple[int, Exception] | None = None,
    ) -> None:
        self.sources = sources
        self._pages = pages if pages is not None else [_synthetic_image()]
        self._raise_at_index = raise_at_index
        self.closed = False
        self.acquire_iter_calls: list[tuple[str, ScanConfig]] = []

    @property
    def backend_name(self) -> str:
        return "sane"

    def list_sources(self) -> list[str]:
        return list(self.sources)

    def acquire(self, source: str, config: ScanConfig) -> list[np.ndarray]:
        return list(self.acquire_iter(source, config))

    def acquire_iter(self, source: str, config: ScanConfig):
        self.acquire_iter_calls.append((source, config))
        for i, page in enumerate(self._pages):
            if self._raise_at_index is not None and self._raise_at_index[0] == i:
                raise self._raise_at_index[1]
            yield page

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
    scanner: FakeAdfScanner | None,
    saas_handler,
    *,
    paired: bool = True,
    scanner_factory_raises: Exception | None = None,
) -> TestClient:
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    if paired:
        save_credentials(_sample_creds(), tmp_path)

    def _scanner_factory():
        if scanner_factory_raises is not None:
            raise scanner_factory_raises
        return scanner

    def _saas_factory(base_url: str) -> SaasClient:
        return SaasClient(
            base_url,
            http_client=httpx.Client(transport=httpx.MockTransport(saas_handler)),
        )

    app.dependency_overrides[get_scanner_factory] = lambda: _scanner_factory
    app.dependency_overrides[get_saas_client_factory] = lambda: _saas_factory
    return TestClient(app)


def _saas_paginated_handler(start_page_id: int = 100):
    """SaaS que devuelve un page_id incremental por upload."""
    state = {"next_id": start_page_id, "next_index": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/pages") and req.method == "POST":
            pid = state["next_id"]
            idx = state["next_index"]
            state["next_id"] += 1
            state["next_index"] += 1
            return httpx.Response(
                201,
                json={
                    "created": [
                        {
                            "id": pid,
                            "batch_id": 42,
                            "page_index": idx,
                            "image_path": f"1/42/{pid}.png",
                            "is_excluded": False,
                            "review_reason": None,
                            "fields": {},
                            "flags": {},
                        }
                    ],
                    "batch_page_count": idx + 1,
                },
            )
        return httpx.Response(404, json={"detail": "ruta inesperada"})

    return handler


def _parse_ndjson(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_scan_adf_happy_three_pages(tmp_path: Path) -> None:
    """3 páginas en el ADF → started + 3× page_uploaded + completed."""
    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(s) for s in (1, 2, 3)],
    )
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    events = _parse_ndjson(resp.text)
    assert [e["event"] for e in events] == [
        "started",
        "page_uploaded",
        "page_uploaded",
        "page_uploaded",
        "completed",
    ]
    # Detalle por página
    uploads = [e for e in events if e["event"] == "page_uploaded"]
    assert [u["page_index"] for u in uploads] == [0, 1, 2]
    assert [u["page_id"] for u in uploads] == [100, 101, 102]
    assert [u["batch_page_count"] for u in uploads] == [1, 2, 3]
    # Resumen final
    completed = events[-1]
    assert completed == {"event": "completed", "total": 3}


def test_scan_adf_uses_adf_source_type(tmp_path: Path) -> None:
    """source_type='adf' llega al ScanConfig (no flatbed)."""
    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(1)],
    )
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    client.post(
        "/scan-adf-and-upload",
        json={
            "scanner_name": "dev:001",
            "batch_id": 42,
            "resolution": 600,
            "mode": "Gray",
        },
    )

    assert len(scanner.acquire_iter_calls) == 1
    source, config = scanner.acquire_iter_calls[0]
    assert source == "dev:001"
    assert config.resolution == 600
    assert config.mode == "Gray"
    assert config.source_type == "adf"


def test_scan_adf_closes_scanner(tmp_path: Path) -> None:
    """scanner.close() se llama incluso en happy path."""
    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(1), _synthetic_image(2)],
    )
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert scanner.closed is True


# ---------------------------------------------------------------------------
# auth + validación
# ---------------------------------------------------------------------------


def test_scan_adf_unpaired_returns_401(tmp_path: Path) -> None:
    """Sin pairing: 401 antes de abrir el stream (no NDJSON)."""
    scanner = FakeAdfScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_paginated_handler(), paired=False)

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 401
    assert scanner.acquire_iter_calls == []


def test_scan_adf_validation_missing_batch_id(tmp_path: Path) -> None:
    scanner = FakeAdfScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    resp = client.post("/scan-adf-and-upload", json={"scanner_name": "dev:001"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# errores antes de iterar
# ---------------------------------------------------------------------------


def test_scan_adf_unknown_scanner_returns_404(tmp_path: Path) -> None:
    """Scanner inexistente: 404 sin abrir stream (validación previa)."""
    scanner = FakeAdfScanner(sources=["dev:001"])
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "no:existe", "batch_id": 42},
    )
    assert resp.status_code == 404
    assert scanner.acquire_iter_calls == []


def test_scan_adf_no_backends_returns_503(tmp_path: Path) -> None:
    """Si scanner_factory levanta RuntimeError (SANE/TWAIN ausente): 503."""
    client = _client(
        tmp_path,
        scanner=None,
        saas_handler=_saas_paginated_handler(),
        scanner_factory_raises=RuntimeError("sin backends"),
    )

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# errores a mitad de stream
# ---------------------------------------------------------------------------


def test_scan_adf_acquire_raises_mid_stream(tmp_path: Path) -> None:
    """acquire_iter falla en la página 2 → 1 uploaded + error + cierre."""
    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(1), _synthetic_image(2), _synthetic_image(3)],
        raise_at_index=(2, RuntimeError("paper jam")),
    )
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )

    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    event_types = [e["event"] for e in events]
    assert event_types == [
        "started",
        "page_uploaded",  # página 0 OK
        "page_uploaded",  # página 1 OK
        "error",  # antes de yield la página 2
    ]
    assert "paper jam" in events[-1]["detail"]
    assert events[-1]["code"] == "scan_error"
    assert scanner.closed is True


def test_scan_adf_saas_rejects_upload_mid_stream(tmp_path: Path) -> None:
    """SaaS devuelve 409 al subir la página 2 → 1 uploaded + error."""
    upload_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        upload_count["n"] += 1
        if upload_count["n"] >= 2:
            return httpx.Response(409, json={"detail": "Lote en ejecución"})
        return httpx.Response(
            201,
            json={
                "created": [
                    {
                        "id": 100,
                        "batch_id": 42,
                        "page_index": 0,
                        "image_path": "1/42/100.png",
                        "is_excluded": False,
                        "review_reason": None,
                        "fields": {},
                        "flags": {},
                    }
                ],
                "batch_page_count": 1,
            },
        )

    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(1), _synthetic_image(2), _synthetic_image(3)],
    )
    client = _client(tmp_path, scanner, handler)

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    event_types = [e["event"] for e in events]
    assert event_types == ["started", "page_uploaded", "error"]
    err = events[-1]
    assert err["code"] == "upload_error"
    assert err["status_code"] == 409
    assert "ejecución" in err["detail"].lower()
    assert scanner.closed is True


def test_scan_adf_saas_unavailable_mid_stream(tmp_path: Path) -> None:
    """SaaS inalcanzable → error code='saas_unavailable'."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    scanner = FakeAdfScanner(
        sources=["dev:001"],
        pages=[_synthetic_image(1)],
    )
    client = _client(tmp_path, scanner, handler)

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    assert events[0]["event"] == "started"
    assert events[-1]["event"] == "error"
    assert events[-1]["code"] == "saas_unavailable"
    assert scanner.closed is True


def test_scan_adf_empty_adf_returns_completed_total_zero(tmp_path: Path) -> None:
    """ADF vacío (yield 0 páginas) → started + completed total=0 (caso límite)."""
    scanner = FakeAdfScanner(sources=["dev:001"], pages=[])
    client = _client(tmp_path, scanner, _saas_paginated_handler())

    resp = client.post(
        "/scan-adf-and-upload",
        json={"scanner_name": "dev:001", "batch_id": 42},
    )
    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    assert [e["event"] for e in events] == ["started", "completed"]
    assert events[-1]["total"] == 0
