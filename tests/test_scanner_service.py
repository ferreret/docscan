"""Tests del servicio de escáner."""

from __future__ import annotations

import os
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
            return types.SimpleNamespace(returncode=1, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(
            subprocess,
            "Popen",
            _fake_popen(pages=0, returncode=1, stderr="scanimage: no such device"),
        )
        scanner = SaneScanner()
        try:
            with pytest.raises(RuntimeError, match="no such device"):
                scanner.acquire("nonexistent_device", ScanConfig())
        finally:
            scanner.close()


# ------------------------------------------------------------------
# scanimage: lote por alimentador, tamaño de página y errores
# ------------------------------------------------------------------

# Límites reales del Canon DR-M160 (``scanimage -A``)
_DR_M160_LIMITS = {
    "--page-width": 219.428,
    "--page-height": 355.554,
    "-x": 215.872,
    "-y": 279.364,
}


def _fake_popen(pages: int, returncode: int = 0, stderr: str = "", hang=False):
    """Popen falso que deja ``pages`` PNG donde scanimage los escribiría."""
    import cv2

    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, cmd, stdout=None, stderr=None):
            calls.append(cmd)
            self._err = stderr
            self.returncode = None
            out = next((a for a in cmd if a.startswith("--batch=")), None)
            if out is not None:
                targets = [out.removeprefix("--batch=") % (i + 1) for i in range(pages)]
            else:
                targets = [cmd[cmd.index("-o") + 1]] if pages else []
            img = np.full((20, 10, 3), 255, np.uint8)
            for t in targets:
                cv2.imwrite(t, img)
            if not hang:
                self._finish()

        def _finish(self, code=None):
            self.returncode = returncode if code is None else code
            self._err.write(stderr.encode())

        def poll(self):
            return self.returncode

        def kill(self):
            self._finish(-9)

        def wait(self):
            return self.returncode

    _Proc.calls = calls
    return _Proc


class TestScanimage:
    """SaneScanner.acquire con scanimage simulado (sin hardware)."""

    @pytest.fixture
    def scanner(self, monkeypatch):
        s = SaneScanner()
        monkeypatch.setattr(s, "_device_limits", lambda source: _DR_M160_LIMITS)
        return s

    def _popen(self, monkeypatch, **kwargs):
        import subprocess

        fake = _fake_popen(**kwargs)
        monkeypatch.setattr(subprocess, "Popen", fake)
        return fake

    def test_adf_un_solo_scanimage_por_lote(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=5)
        images = scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))
        assert len(images) == 5
        (cmd,) = fake.calls
        assert any(a.startswith("--batch=") for a in cmd)
        assert cmd[cmd.index("--source") + 1] == "ADF Front"

    def test_duplex_usa_adf_duplex(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=4)
        scanner.acquire("canon_dr:x", ScanConfig(source_type="adf", duplex=True))
        cmd = fake.calls[0]
        assert cmd[cmd.index("--source") + 1] == "ADF Duplex"

    def test_la_fuente_del_dialogo_manda(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=2)
        cfg = ScanConfig(source_type="flatbed", extra_options={"source": "ADF Duplex"})
        assert len(scanner.acquire("canon_dr:x", cfg)) == 2
        cmd = fake.calls[0]
        assert cmd[cmd.index("--source") + 1] == "ADF Duplex"
        assert any(a.startswith("--batch=") for a in cmd)

    def test_flatbed_del_dialogo_gana_al_adf_del_panel(self, scanner, monkeypatch):
        """«Flatbed» en el diálogo con ADF en ⚙: una página, sin --batch."""
        fake = self._popen(monkeypatch, pages=1)
        cfg = ScanConfig(source_type="adf", extra_options={"source": "Flatbed"})
        assert len(scanner.acquire("escl:x", cfg)) == 1
        cmd = fake.calls[0]
        assert "-o" in cmd and not any(a.startswith("--batch") for a in cmd)
        assert cmd[cmd.index("--source") + 1] == "Flatbed"

    def test_otros_nombres_de_alimentador(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=3)
        cfg = ScanConfig(extra_options={"source": "Automatic Document Feeder"})
        assert len(scanner.acquire("dev", cfg)) == 3
        assert any(a.startswith("--batch=") for a in fake.calls[0])

    def test_plano_una_pagina_sin_batch(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=1)
        assert len(scanner.acquire("dev", ScanConfig(source_type="flatbed"))) == 1
        cmd = fake.calls[0]
        assert "-o" in cmd and not any(a.startswith("--batch") for a in cmd)
        assert "--source" not in cmd

    def test_a4_por_defecto(self, scanner, monkeypatch):
        """Sin elegir tamaño el alimentador escanea A4, no la Carta del driver."""
        fake = self._popen(monkeypatch, pages=1)
        scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))
        cmd = fake.calls[0]
        assert cmd[cmd.index("--page-width") + 1] == "210"
        assert cmd[cmd.index("--page-height") + 1] == "297"
        assert cmd[cmd.index("-x") + 1] == "210"
        assert cmd[cmd.index("-y") + 1] == "297"

    def test_tamano_del_dialogo(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=1)
        cfg = ScanConfig(source_type="adf", extra_options={"page_size": "Letter"})
        scanner.acquire("canon_dr:x", cfg)
        cmd = fake.calls[0]
        assert cmd[cmd.index("--page-height") + 1] == "279.4"

    def test_tamano_del_escaner(self, scanner, monkeypatch):
        fake = self._popen(monkeypatch, pages=1)
        cfg = ScanConfig(source_type="adf", extra_options={"page_size": ""})
        scanner.acquire("canon_dr:x", cfg)
        cmd = fake.calls[0]
        assert "--page-height" not in cmd and "-y" not in cmd

    def test_legal_se_recorta_al_maximo_del_dispositivo(self, scanner):
        opts = scanner._geometry_options("canon_dr:x", "Legal")
        assert opts[opts.index("--page-height") + 1] == "355.554"
        assert opts[opts.index("-y") + 1] == "355.554"

    def test_escaner_plano_solo_area(self, monkeypatch):
        s = SaneScanner()
        monkeypatch.setattr(s, "_device_limits", lambda src: {"-x": 216.0, "-y": 290.0})
        assert s._geometry_options("plano", "A4") == ["-x", "210", "-y", "290"]

    def test_sin_geometria_conocida_no_se_toca(self, monkeypatch):
        s = SaneScanner()
        monkeypatch.setattr(s, "_device_limits", lambda src: {})
        assert s._geometry_options("raro", "A4") == []

    def test_limites_desde_scanimage_A(self, monkeypatch):
        import subprocess
        import types

        salida = (
            "    --page-width 0..219.428mm (in steps of 0.0211639) [215.872]\n"
            "    --page-height 0..355.554mm (in steps of 0.0211639) [279.364]\n"
            "    -x 0..215.872mm (in steps of 0.0211639) [215.872]\n"
            "    -y 0..279.364mm (in steps of 0.0211639) [279.364]\n"
        )
        llamadas = []

        def _run(cmd, **kw):
            llamadas.append(cmd)
            return types.SimpleNamespace(
                returncode=0, stdout=salida.encode(), stderr=b""
            )

        monkeypatch.setattr(subprocess, "run", _run)
        s = SaneScanner()
        assert s._device_limits("canon_dr:x") == _DR_M160_LIMITS
        s._device_limits("canon_dr:x")
        assert len(llamadas) == 1, "se cachea por dispositivo"

    def test_fin_de_papel_es_final_normal(self, scanner, monkeypatch):
        self._popen(
            monkeypatch,
            pages=3,
            stderr="Scanning page 4\nscanimage: sane_start: Document feeder out of documents\n",
        )
        assert len(scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))) == 3

    def test_atasco_a_mitad_de_lote_no_es_silencioso(self, scanner, monkeypatch):
        from app.services.scanner_service import ScanIncompleteError

        self._popen(
            monkeypatch,
            pages=2,
            returncode=1,
            stderr=(
                "scanimage: rounded value of br-y from 297 to 296.994\n"
                "Scanning page 3\n"
                "scanimage: sane_read: Document feeder jammed\n"
            ),
        )
        with pytest.raises(ScanIncompleteError) as exc:
            scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))
        assert len(exc.value.images) == 2
        assert "2 página(s)" in str(exc.value)
        assert "Document feeder jammed" in str(exc.value)
        assert "rounded" not in str(exc.value)

    def test_sin_papel_al_empezar(self, scanner, monkeypatch):
        self._popen(
            monkeypatch,
            pages=0,
            returncode=1,
            stderr="scanimage: sane_start: Document feeder out of documents\n",
        )
        with pytest.raises(RuntimeError, match="out of documents"):
            scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))

    def test_escaner_colgado_se_aborta(self, scanner, monkeypatch):
        from app.services.scanner_service import ScanIncompleteError

        self._popen(monkeypatch, pages=1, hang=True)
        monkeypatch.setattr(SaneScanner, "IDLE_TIMEOUT", 0)
        with pytest.raises(ScanIncompleteError, match="sin respuesta"):
            scanner.acquire("canon_dr:x", ScanConfig(source_type="adf"))

    def test_scanimage_error_filtra_progreso(self):
        from app.services.scanner_service import _scanimage_error

        assert _scanimage_error("Scanning page 1\nScanned page 1.\n") == ""
        assert (
            _scanimage_error("scanimage: a\nScanning page 2\nscanimage: b\n") == "a; b"
        )


# ------------------------------------------------------------------
# Página a página y cancelación (lote 4: E1 y E3)
# ------------------------------------------------------------------

_FAKE_SCANIMAGE = r"""#!/bin/bash
# scanimage falso: escribe cada página en «.part» y la renombra, como el real.
for a in "$@"; do
  case "$a" in
    --batch=*) pat="${a#--batch=}" ;;
    -A) exit 0 ;;
  esac
done
trap 'echo "scanimage: received signal 15" >&2; exit 2' TERM
for i in $(seq 1 "$FAKE_PAGES"); do
  f=$(printf "$pat" "$i")
  cp "$FAKE_SRC" "$f.part"
  sleep 0.2 & wait $!
  mv "$f.part" "$f"
  sleep 0.6 & wait $!
done
"""


class TestPaginaAPaginaYCancelar:
    """Con un scanimage falso de verdad (subproceso, señales y ficheros)."""

    @pytest.fixture
    def scanner(self, monkeypatch, tmp_path):
        import cv2

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        script = bin_dir / "scanimage"
        script.write_text(_FAKE_SCANIMAGE)
        script.chmod(0o755)
        src = tmp_path / "hoja.png"
        cv2.imwrite(str(src), np.full((20, 10, 3), 255, np.uint8))
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        monkeypatch.setenv("FAKE_SRC", str(src))
        s = SaneScanner()
        monkeypatch.setattr(s, "_device_limits", lambda source: {})
        return s

    def test_entrega_cada_pagina_en_cuanto_llega(self, scanner, monkeypatch):
        import time

        monkeypatch.setenv("FAKE_PAGES", "3")
        llegadas: list[float] = []
        images = scanner.acquire(
            "fake:dev",
            ScanConfig(source_type="adf"),
            on_page=lambda img: llegadas.append(time.monotonic()),
        )
        fin = time.monotonic()
        assert len(images) == 3 and len(llegadas) == 3
        # La primera llega mientras el escáner sigue con las otras dos.
        assert fin - llegadas[0] > 1.0

    def test_cancelar_conserva_las_paginas_completas(self, scanner, monkeypatch):
        import time

        monkeypatch.setenv("FAKE_PAGES", "10")
        recibidas: list[np.ndarray] = []
        inicio = time.monotonic()
        images = scanner.acquire(
            "fake:dev",
            ScanConfig(source_type="adf"),
            on_page=recibidas.append,
            should_stop=lambda: len(recibidas) >= 2,
        )
        assert time.monotonic() - inicio < 6  # 10 hojas tardarían ~8 s
        assert 2 <= len(images) < 10
        assert len(recibidas) == len(images)

    def test_un_fallo_en_on_page_no_deja_el_escaner_corriendo(
        self, scanner, monkeypatch
    ):
        import subprocess

        monkeypatch.setenv("FAKE_PAGES", "10")
        procesos: list[subprocess.Popen] = []
        real_popen = subprocess.Popen

        def popen(*a, **kw):
            procesos.append(real_popen(*a, **kw))
            return procesos[-1]

        monkeypatch.setattr(subprocess, "Popen", popen)

        def roto(img):
            raise RuntimeError("roto")

        with pytest.raises(RuntimeError, match="roto"):
            scanner.acquire("fake:dev", ScanConfig(source_type="adf"), on_page=roto)
        assert procesos and all(p.poll() is not None for p in procesos)
