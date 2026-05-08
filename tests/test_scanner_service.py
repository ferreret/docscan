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


class _FakeScanner(BaseScanner):
    """BaseScanner con ``acquire()`` simulado para validar el contrato
    de ``acquire_iter`` sin requerir SANE/TWAIN/WIA reales."""

    def __init__(self, pages: list[np.ndarray]) -> None:
        self._pages = pages
        self.acquire_calls = 0

    @property
    def backend_name(self) -> str:
        return "fake"

    def list_sources(self) -> list[str]:
        return ["fake-source"]

    def acquire(self, source, config):
        self.acquire_calls += 1
        return list(self._pages)

    def close(self) -> None:
        pass


class TestAcquireIterContract:
    """Hito 8 sprint local-agent: contrato de ``BaseScanner.acquire_iter``.

    Las subclases que NO sobreescriban ``acquire_iter`` heredan la
    implementación por defecto que materializa ``acquire()``. Así los
    backends Twain/Wia siguen funcionando sin tocar nada.
    """

    def _pages(self, n: int) -> list[np.ndarray]:
        return [np.zeros((10, 10, 3), dtype=np.uint8) for _ in range(n)]

    def test_default_iter_yields_same_pages_as_acquire(self):
        pages = self._pages(3)
        scanner = _FakeScanner(pages)

        emitted = list(scanner.acquire_iter("fake-source", ScanConfig()))

        assert len(emitted) == 3
        assert all(arr.shape == (10, 10, 3) for arr in emitted)

    def test_default_iter_delegates_to_acquire(self):
        scanner = _FakeScanner(self._pages(2))

        list(scanner.acquire_iter("fake-source", ScanConfig()))

        assert scanner.acquire_calls == 1

    def test_default_iter_empty_list(self):
        scanner = _FakeScanner([])

        emitted = list(scanner.acquire_iter("fake-source", ScanConfig()))

        assert emitted == []

    def test_acquire_still_returns_list(self):
        """Subclases existentes que usan ``acquire()`` reciben una lista,
        no un iterador. El contrato externo no cambia con el refactor."""
        scanner = _FakeScanner(self._pages(2))

        result = scanner.acquire("fake-source", ScanConfig())

        assert isinstance(result, list)
        assert len(result) == 2
