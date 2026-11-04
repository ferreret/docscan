"""Tests del registro de salida y de la retirada de transferencias fallidas.

Paridad con FlexibarNET10 v1.27: una transferencia que falla a medias no deja
salida parcial. Antes, el reintento creaba duplicados ``_1`` y, con «Fusionar»,
volvía a anexar al PDF/TIFF las páginas del intento fallido.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pymupdf
import pytest

from app.pipeline.page_context import AppContext, BatchContext
from app.services.output_journal import BACKUP_MARK, OutputJournal
from app.services.script_engine import ScriptEngine
from app.services.transfer_flow import execute_transfer
from app.services.transfer_service import TransferConfig, TransferService


def _backups(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if BACKUP_MARK in p.name]


@pytest.fixture
def pages(tmp_path: Path) -> list[dict]:
    out = []
    for i in range(3):
        path = tmp_path / "src" / f"p{i}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), np.full((40, 30, 3), 60 * i, np.uint8))
        out.append({"image_path": str(path), "page_index": i, "fields": {}})
    return out


class TestOutputJournal:
    def test_rollback_borra_lo_creado_y_las_carpetas_nuevas(self, tmp_path):
        journal = OutputJournal()
        dest = tmp_path / "out" / "sub"
        journal.mkdir(dest)
        f = dest / "a.txt"
        journal.prepare(f)
        f.write_text("nuevo")

        assert journal.rollback() == []
        assert not (tmp_path / "out").exists()

    def test_rollback_restaura_lo_modificado(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original")
        journal = OutputJournal()
        journal.prepare(f)
        f.write_text("pisado")
        journal.prepare(f)  # una segunda escritura no pisa la copia
        f.write_text("pisado otra vez")

        journal.rollback()
        assert f.read_text() == "original"
        assert _backups(tmp_path) == []

    def test_no_borra_carpetas_con_contenido_ajeno(self, tmp_path):
        journal = OutputJournal()
        dest = tmp_path / "out"
        journal.mkdir(dest)
        (dest / "ajeno.txt").write_text("de otro")

        journal.rollback()
        assert (dest / "ajeno.txt").exists()

    def test_commit_conserva_la_salida_y_borra_las_copias(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original")
        journal = OutputJournal()
        journal.prepare(f)
        f.write_text("nuevo")

        journal.commit()
        assert journal.rollback() == []  # ya confirmado: no hace nada
        assert f.read_text() == "nuevo"
        assert _backups(tmp_path) == []


class TestTransferenciaQueFallaAMedias:
    def test_carpeta_retira_las_paginas_ya_copiadas(self, tmp_path, pages):
        dest = tmp_path / "out"
        real_copy = shutil.copy2
        calls = {"n": 0}

        def copy_que_falla(src, dst):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("disco lleno")
            return real_copy(src, dst)

        with patch("app.services.transfer_service.shutil.copy2", copy_que_falla):
            result = TransferService().transfer(
                pages, TransferConfig(destination=str(dest))
            )

        assert not result.success
        assert result.files_transferred == 0
        assert any("disco lleno" in e for e in result.errors)
        assert not dest.exists()

    def test_fusionar_no_anexa_dos_veces_al_reintentar(self, tmp_path, pages):
        """Dos documentos van al mismo PDF: el 1.º se anexa y el 2.º falla.

        Antes, el PDF se quedaba con las páginas del 1.º y el reintento las
        volvía a anexar. Ahora vuelve a su contenido anterior.
        """
        dest = tmp_path / "out"
        config = TransferConfig(
            destination=str(dest),
            mode="pdf",
            grouping="document",
            collision_policy="merge",
            filename_pattern="archivo",
        )
        service = TransferService()
        assert service.transfer(pages[:1], config).success
        pdf = dest / "archivo.pdf"
        with pymupdf.open(pdf) as doc:
            assert doc.page_count == 1

        lote = [dict(p) for p in pages]
        lote[0].update(is_separator=True, separator_value="A")
        lote[2].update(is_separator=True, separator_value="B")
        real_write = TransferService._write_pdf
        calls = {"n": 0}

        def write_que_falla(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("roto")
            return real_write(self, *args, **kwargs)

        with patch.object(TransferService, "_write_pdf", write_que_falla):
            assert not service.transfer(lote, config).success

        assert calls["n"] == 2  # el primer documento sí llegó a anexarse
        with pymupdf.open(pdf) as doc:
            assert doc.page_count == 1
        assert _backups(dest) == []

    def test_sobrescribir_restaura_el_fichero_anterior(self, tmp_path, pages):
        dest = tmp_path / "out"
        dest.mkdir()
        previo = dest / "batch_0_page_0000.png"
        previo.write_bytes(b"contenido previo")
        real_copy = shutil.copy2
        calls = {"n": 0}

        def copy_que_falla(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:  # la 1.ª es la copia de seguridad
                real_copy(src, dst)  # pisa el previo...
                raise OSError("fallo tras escribir")
            return real_copy(src, dst)

        config = TransferConfig(destination=str(dest), collision_policy="overwrite")
        with patch("app.services.transfer_service.shutil.copy2", copy_que_falla):
            assert not TransferService().transfer(pages, config).success

        assert previo.read_bytes() == b"contenido previo"
        assert sorted(p.name for p in dest.iterdir()) == ["batch_0_page_0000.png"]

    def test_transferencia_correcta_no_deja_copias(self, tmp_path, pages):
        dest = tmp_path / "out"
        dest.mkdir()
        (dest / "batch_0_page_0000.png").write_bytes(b"x")
        config = TransferConfig(destination=str(dest), collision_policy="overwrite")
        assert TransferService().transfer(pages, config).success
        assert _backups(dest) == []


class TestScriptAvanzadoQueFalla:
    def test_retira_la_salida_de_la_transferencia_simple(self, tmp_path, pages):
        engine = ScriptEngine()
        engine.compile_script(
            "on_transfer_advanced",
            "def on_transfer_advanced(app, batch, pages=None, result=None):\n"
            "    raise RuntimeError('LIS caído')\n",
        )
        dest = tmp_path / "out"
        result = execute_transfer(
            transfer_service=TransferService(),
            config=TransferConfig(destination=str(dest)),
            pages=pages,
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts={"app": AppContext(id=1), "batch": BatchContext(id=7)},
        )
        assert not result.success
        assert result.files_transferred == 0
        assert any("LIS caído" in e for e in result.errors)
        assert any("retirado" in e for e in result.errors)
        assert not dest.exists()

    def test_si_el_avanzado_va_bien_la_salida_se_queda(self, tmp_path, pages):
        engine = ScriptEngine()
        engine.compile_script(
            "on_transfer_advanced",
            "def on_transfer_advanced(app, batch, pages=None, result=None):\n"
            "    return True\n",
        )
        dest = tmp_path / "out"
        result = execute_transfer(
            transfer_service=TransferService(),
            config=TransferConfig(destination=str(dest)),
            pages=pages,
            batch_fields={},
            batch_id=7,
            script_engine=engine,
            contexts={"app": AppContext(id=1), "batch": BatchContext(id=7)},
        )
        assert result.success
        assert len([p for p in dest.rglob("*") if p.is_file()]) == 3
        assert _backups(dest) == []
