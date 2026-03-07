"""Tests del servicio de escáner."""

from __future__ import annotations

import platform

import numpy as np
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
    import sane
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
    def test_backend_name(self):
        scanner = SaneScanner()
        assert scanner.backend_name == "sane"
        scanner.close()

    def test_list_sources(self):
        scanner = SaneScanner()
        try:
            sources = scanner.list_sources()
            assert isinstance(sources, list)
            # Puede estar vacío si no hay escáneres conectados
            for source in sources:
                assert isinstance(source, str)
        finally:
            scanner.close()

    def test_acquire_no_device(self):
        """Intentar escanear un dispositivo inexistente debe fallar."""
        scanner = SaneScanner()
        try:
            with pytest.raises(Exception):
                scanner.acquire("nonexistent_device", ScanConfig())
        finally:
            scanner.close()
