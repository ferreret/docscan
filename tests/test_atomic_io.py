"""Tests de la escritura atómica (temp + rename)."""

from __future__ import annotations

import os
import sys

import pytest

from app.utils.atomic_io import atomic_write_bytes, atomic_write_text


class TestAtomicWrite:
    def test_crea_fichero_nuevo(self, tmp_path):
        target = tmp_path / "nuevo.json"

        atomic_write_text(target, '{"a": 1}')

        assert target.read_text(encoding="utf-8") == '{"a": 1}'

    def test_crea_directorios_intermedios(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "fichero.txt"

        atomic_write_text(target, "hola")

        assert target.read_text(encoding="utf-8") == "hola"

    def test_sobrescribe_contenido_previo(self, tmp_path):
        target = tmp_path / "prefs.json"
        target.write_text("viejo", encoding="utf-8")

        atomic_write_text(target, "nuevo")

        assert target.read_text(encoding="utf-8") == "nuevo"

    def test_bytes_y_texto_coinciden(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"

        atomic_write_bytes(a, "áéí".encode("utf-8"))
        atomic_write_text(b, "áéí")

        assert a.read_bytes() == b.read_bytes()

    def test_no_deja_temporales(self, tmp_path):
        target = tmp_path / "datos.json"

        atomic_write_text(target, "x" * 1000)

        assert [p.name for p in tmp_path.iterdir()] == ["datos.json"]

    def test_fallo_a_mitad_conserva_el_original(self, tmp_path, monkeypatch):
        """Si el reemplazo falla, el fichero previo queda intacto."""
        target = tmp_path / "prefs.json"
        target.write_text("contenido bueno", encoding="utf-8")

        def boom(*args, **kwargs):
            raise OSError("disco lleno")

        monkeypatch.setattr(os, "replace", boom)

        with pytest.raises(OSError):
            atomic_write_text(target, "contenido a medias")

        assert target.read_text(encoding="utf-8") == "contenido bueno"
        # Y tampoco deja basura alrededor.
        assert [p.name for p in tmp_path.iterdir()] == ["prefs.json"]

    @pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")
    def test_aplica_permisos(self, tmp_path):
        target = tmp_path / "secreto.enc"

        atomic_write_bytes(target, b"cifrado", chmod=0o600)

        assert target.stat().st_mode & 0o777 == 0o600
