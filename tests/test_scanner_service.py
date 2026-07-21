"""Tests del servicio de escáner."""

from __future__ import annotations

import platform

import pytest

from app.services.scanner_service import (
    BaseScanner,
    SaneScanner,
    ScanConfig,
    create_scanner,
    get_available_backends,
)

_SYSTEM = platform.system()
_HAS_SANE = False
try:
    import sane  # noqa: F401  # sonda de disponibilidad del backend

    _HAS_SANE = True
except ImportError:
    pass


class TestScanConfig:
    def test_defaults(self):
        config = ScanConfig()
        assert config.resolution == 300
        assert config.mode == "Color"
        assert config.duplex is False

    def test_custom(self):
        config = ScanConfig(resolution=600, mode="Gray", duplex=True)
        assert config.resolution == 600


class TestBackendDiscovery:
    def test_get_available_backends(self):
        backends = get_available_backends()
        assert isinstance(backends, list)
        if _SYSTEM == "Linux" and _HAS_SANE:
            assert "sane" in backends

    def test_create_scanner_auto(self):
        backends = get_available_backends()
        if not backends:
            pytest.skip("No hay backends disponibles")
        scanner = create_scanner()
        assert isinstance(scanner, BaseScanner)

    def test_create_scanner_invalid_backend(self):
        # Si el backend no existe, debe usar alternativa o fallar
        backends = get_available_backends()
        if backends:
            scanner = create_scanner(backend="nonexistent")
            assert isinstance(scanner, BaseScanner)
        else:
            with pytest.raises(RuntimeError):
                create_scanner(backend="nonexistent")


@pytest.mark.skipif(not _HAS_SANE, reason="python-sane no disponible")
class TestSaneScanner:
    """Tests del wrapper SaneScanner con la capa SANE mockeada.

    `sane.get_devices()` enumera hardware (incluidos escáneres de red) y puede
    tardar decenas de segundos o colgarse indefinidamente segun el estado del
    equipo. Se mockea el modulo `sane` para que los tests sean deterministas y
    rapidos; la integracion con SANE real se valida en smoke tests manuales.
    """

    @pytest.fixture(autouse=True)
    def _mock_sane(self, monkeypatch):
        import sane

        monkeypatch.setattr(sane, "init", lambda: (1, 1, 0, 0), raising=False)
        monkeypatch.setattr(sane, "exit", lambda: None, raising=False)
        monkeypatch.setattr(
            sane,
            "get_devices",
            lambda *a, **k: [("mock:dev0", "ACME", "ScanMaster", "scanner")],
            raising=False,
        )

    def test_backend_name(self):
        scanner = SaneScanner()
        assert scanner.backend_name == "sane"
        scanner.close()

    def test_list_sources(self):
        scanner = SaneScanner()
        try:
            sources = scanner.list_sources()
            assert sources == ["mock:dev0"]
        finally:
            scanner.close()

    def test_acquire_no_device(self, monkeypatch):
        """Un escaneo que falla (returncode != 0) debe lanzar RuntimeError."""
        import subprocess
        import types

        def _fake_run(*args, **kwargs):
            return types.SimpleNamespace(
                returncode=1, stdout=b"", stderr=b"scanimage: no such device"
            )

        monkeypatch.setattr(subprocess, "run", _fake_run)
        scanner = SaneScanner()
        try:
            with pytest.raises(RuntimeError):
                scanner.acquire("nonexistent_device", ScanConfig())
        finally:
            scanner.close()
