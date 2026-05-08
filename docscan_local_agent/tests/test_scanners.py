"""Tests del endpoint GET /scanners.

Mockeamos ``scanner_factory`` con un FakeScanner para no depender de
SANE/TWAIN/WIA reales en CI. La integración con el backend real se
verifica en el smoke manual al final del hito.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docscan_local_agent.credentials import AgentCredentials, save_credentials
from docscan_local_agent.deps import (
    get_scanner_factory,
    get_settings,
)
from docscan_local_agent.main import create_app
from docscan_local_agent.routers.scanners import (
    _invalidate_cache,
    _invalidate_options_cache,
)
from docscan_local_agent.settings import AgentSettings


@pytest.fixture(autouse=True)
def _reset_cache():
    """Cada test arranca con cache limpio.

    Tanto el cache de ``GET /scanners`` (workaround FD_SETSIZE de
    libsane-pixma) como el de ``GET /scanners/{name}/options`` se
    resetean para no polucionar tests siguientes.
    """
    _invalidate_cache()
    _invalidate_options_cache()
    yield
    _invalidate_cache()
    _invalidate_options_cache()


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
        device_options: dict[str, list] | None = None,
        raise_on_options: Exception | None = None,
    ) -> None:
        self.sources = sources
        self._backend = backend
        self._raise = raise_on_list
        self._device_options = device_options or {}
        self._raise_on_options = raise_on_options
        self.closed = False

    @property
    def backend_name(self) -> str:
        return self._backend

    def list_sources(self) -> list[str]:
        if self._raise is not None:
            raise self._raise
        return list(self.sources)

    def get_device_options(self, source: str) -> list:
        if self._raise_on_options is not None:
            raise self._raise_on_options
        return list(self._device_options.get(source, []))

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


# ---------------------------------------------------------------------------
# cache (workaround bug FD_SETSIZE de libsane-pixma)
# ---------------------------------------------------------------------------


def test_scanners_caches_between_calls(tmp_path: Path) -> None:
    """Dos GET /scanners seguidos sólo invocan list_sources() una vez."""
    calls: list[int] = []

    class CountingScanner(FakeScanner):
        def list_sources(self) -> list[str]:  # type: ignore[override]
            calls.append(1)
            return super().list_sources()

    scanner = CountingScanner(sources=["s1", "s2"])
    client = _client_with_scanner(tmp_path, scanner)

    r1 = client.get("/scanners")
    r2 = client.get("/scanners")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    assert sum(calls) == 1


def test_scanners_refresh_true_bypasses_cache(tmp_path: Path) -> None:
    """?refresh=true fuerza re-enumeración aunque el cache esté caliente."""
    calls: list[int] = []

    class CountingScanner(FakeScanner):
        def list_sources(self) -> list[str]:  # type: ignore[override]
            calls.append(1)
            return super().list_sources()

    scanner = CountingScanner(sources=["s1"])
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners")  # 1ª llamada — popula cache
    client.get("/scanners?refresh=true")  # fuerza re-enumeración
    assert sum(calls) == 2


def test_scanners_cache_not_populated_on_error(tmp_path: Path) -> None:
    """Si list_sources lanza, no debemos cachear el error."""
    failing = FakeScanner(sources=[], raise_on_list=RuntimeError("usb gone"))
    client = _client_with_scanner(tmp_path, failing)

    r1 = client.get("/scanners")
    assert r1.status_code == 500

    # El siguiente GET debe volver a invocar el factory (no servir error cacheado).
    # Lo verificamos cambiando el override a un scanner sano y comprobando 200.
    healthy = FakeScanner(sources=["s2"], backend="sane")
    client.app.dependency_overrides[get_scanner_factory] = lambda: lambda: healthy
    r2 = client.get("/scanners")
    assert r2.status_code == 200
    assert r2.json()["scanners"] == [{"name": "s2", "backend": "sane"}]


# ===========================================================================
# GET /scanners/{name}/options — opciones dinámicas del dispositivo
# ===========================================================================
#
# El endpoint delega en ``scanner.get_device_options(source)`` (mismo método
# que el desktop usa para el ScannerConfigDialog) y serializa la lista para
# el frontend. Cache TTL análogo al de /scanners porque abrir el dispositivo
# SANE para query es caro y libsane-pixma sigue acumulando fds.
# ---------------------------------------------------------------------------


def _sample_options() -> dict[str, list[dict]]:
    """Estructura de opciones realista del Canon DR-M160 (subset).

    Replica lo que ``SaneScanner.get_device_options`` devuelve, ya
    serializado a list[dict] (el endpoint del agente lo recibe como
    list[DeviceOption] del desktop pero el FakeScanner ahorra esa capa
    devolviendo dicts directamente — el endpoint los pasa a
    ``DeviceOptionInfo.model_validate`` que acepta tanto el dataclass del
    desktop como un dict equivalente).
    """
    return {
        "canon_dr:libusb:001:010": [
            {
                "name": "resolution",
                "title": "Scan resolution",
                "description": "Sets the resolution of the scanned image.",
                "type": "int",
                "unit": "dpi",
                "constraint": [100, 150, 200, 300, 400, 600],
                "value": 600,
                "is_active": True,
                "is_settable": True,
            },
            {
                "name": "mode",
                "title": "Scan mode",
                "description": "Selects the scan mode (Color/Gray/Lineart).",
                "type": "string",
                "unit": "none",
                "constraint": ["Lineart", "Gray", "Color"],
                "value": "Gray",
                "is_active": True,
                "is_settable": True,
            },
            {
                "name": "source",
                "title": "Scan source",
                "description": "Selects the scan source (such as a document-feeder).",
                "type": "string",
                "unit": "none",
                "constraint": ["ADF Front", "ADF Duplex"],
                "value": "ADF Front",
                "is_active": True,
                "is_settable": True,
            },
        ],
    }


def test_scanner_options_returns_list(tmp_path: Path) -> None:
    """200 con el array de opciones serializado del Canon DR-M160."""
    scanner = FakeScanner(
        sources=["canon_dr:libusb:001:010"],
        device_options=_sample_options(),
    )
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners/canon_dr:libusb:001:010/options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scanner"] == "canon_dr:libusb:001:010"
    assert isinstance(body["options"], list)
    assert len(body["options"]) == 3
    names = [o["name"] for o in body["options"]]
    assert names == ["resolution", "mode", "source"]
    # Tipos serializan como string sin tocar el constraint.
    res = body["options"][0]
    assert res["type"] == "int"
    assert res["unit"] == "dpi"
    assert res["constraint"] == [100, 150, 200, 300, 400, 600]
    assert res["value"] == 600


def test_scanner_options_unpaired_returns_401(tmp_path: Path) -> None:
    """Sin emparejar el agente NO debe ofrecer opciones (mismo guard)."""
    client = _client_with_scanner(
        tmp_path,
        FakeScanner(sources=["s1"], device_options={"s1": []}),
        paired=False,
    )

    resp = client.get("/scanners/s1/options")
    assert resp.status_code == 401


def test_scanner_options_unknown_scanner_returns_404(tmp_path: Path) -> None:
    """Si el scanner_name no aparece en list_sources(), 404 limpio."""
    scanner = FakeScanner(
        sources=["canon_dr:libusb:001:010"],
        device_options=_sample_options(),
    )
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners/epson:fake:999/options")
    assert resp.status_code == 404
    assert "no existe" in resp.json()["detail"].lower()


def test_scanner_options_no_backend_returns_503(tmp_path: Path) -> None:
    """Sistema sin backends de escáner instalados → 503."""
    client = _client_with_scanner(
        tmp_path,
        scanner=None,
        factory_raises=RuntimeError("No hay backends de escáner disponibles"),
    )

    resp = client.get("/scanners/anyname/options")
    assert resp.status_code == 503


def test_scanner_options_get_device_options_raises_returns_500(
    tmp_path: Path,
) -> None:
    """Si get_device_options revienta, 500 con mensaje claro."""
    scanner = FakeScanner(
        sources=["s1"],
        raise_on_options=RuntimeError("USB I/O error"),
    )
    client = _client_with_scanner(tmp_path, scanner)

    resp = client.get("/scanners/s1/options")
    assert resp.status_code == 500
    assert "usb i/o" in resp.json()["detail"].lower()


def test_scanner_options_caches_between_calls(tmp_path: Path) -> None:
    """Dos GET seguidos al mismo scanner sólo invocan get_device_options 1x."""
    calls: list[str] = []

    class CountingScanner(FakeScanner):
        def get_device_options(self, source):  # type: ignore[override]
            calls.append(source)
            return super().get_device_options(source)

    scanner = CountingScanner(
        sources=["s1"],
        device_options={
            "s1": [
                {
                    "name": "x",
                    "title": "X",
                    "description": "",
                    "type": "int",
                    "unit": "none",
                    "constraint": None,
                    "value": 0,
                    "is_active": True,
                    "is_settable": True,
                }
            ]
        },
    )
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners/s1/options")
    client.get("/scanners/s1/options")
    assert calls == ["s1"]


def test_scanner_options_refresh_true_bypasses_cache(tmp_path: Path) -> None:
    """?refresh=true fuerza re-enumeración aunque el cache esté caliente."""
    calls: list[str] = []

    class CountingScanner(FakeScanner):
        def get_device_options(self, source):  # type: ignore[override]
            calls.append(source)
            return super().get_device_options(source)

    scanner = CountingScanner(
        sources=["s1"],
        device_options={"s1": []},
    )
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners/s1/options")
    client.get("/scanners/s1/options?refresh=true")
    assert calls == ["s1", "s1"]


def test_scanner_options_cache_per_scanner(tmp_path: Path) -> None:
    """El cache se indexa por scanner_name — dos scanners se cachean por separado."""
    calls: list[str] = []

    class CountingScanner(FakeScanner):
        def get_device_options(self, source):  # type: ignore[override]
            calls.append(source)
            return super().get_device_options(source)

    scanner = CountingScanner(
        sources=["s1", "s2"],
        device_options={"s1": [], "s2": []},
    )
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners/s1/options")
    client.get("/scanners/s2/options")
    client.get("/scanners/s1/options")  # cacheado
    client.get("/scanners/s2/options")  # cacheado
    assert calls == ["s1", "s2"]


def test_scanner_options_close_called_on_success(tmp_path: Path) -> None:
    """Tras un get_device_options OK, scanner.close() se llama."""
    scanner = FakeScanner(
        sources=["s1"],
        device_options={"s1": []},
    )
    client = _client_with_scanner(tmp_path, scanner)

    client.get("/scanners/s1/options")
    assert scanner.closed is True
