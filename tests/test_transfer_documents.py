"""Tests de la transferencia por documento (lote 6, paridad FlexibarNET10).

Tokens de documento, TIFF/PDF multipágina por documento, hoja separadora
incluida o descartada, script de nombre y validaciones previas.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

from app.services.script_engine import ScriptEngine
from app.services.transfer_flow import (
    FILE_NAME_SCRIPT_ID,
    compile_transfer_scripts,
    execute_transfer,
    validate_before_transfer,
)
from app.services.transfer_service import (
    TransferConfig,
    TransferService,
    document_problems,
    parse_transfer_config,
)
from app.workers.recognition_worker import AppContext, BatchContext


def _pages(tmp_path: Path, marks: list[str | None]) -> list[dict]:
    """Una página por elemento: None = sin separador, str = separador."""
    pages = []
    for i, mark in enumerate(marks):
        img = np.full((40, 30, 3), 255, np.uint8)
        img[5:10, 5:25] = 0
        path = tmp_path / "src" / f"p{i}.png"
        path.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(path), img)
        pages.append(
            {
                "image_path": str(path),
                "page_index": i,
                "fields": {},
                "ocr_text": "",
                "first_barcode": "",
                "is_separator": mark is not None,
                "separator_value": mark or "",
            }
        )
    return pages


def _tiff_frames(path: Path) -> int:
    with Image.open(path) as im:
        return getattr(im, "n_frames", 1)


class TestTokens:
    def test_separator_en_todas_las_paginas_del_documento(self, tmp_path):
        pages = _pages(tmp_path, ["FAC-1", None, "FAC-2", None])
        config = TransferConfig(
            destination=str(tmp_path / "out"),
            create_subdirs=False,
            filename_pattern="{separator}_{document_index}_{page_index}",
        )
        result = TransferService().transfer(pages, config, batch_id=7)
        assert result.success, result.errors
        names = sorted(p.stem for p in (tmp_path / "out").iterdir())
        assert names == ["FAC-1_1_0", "FAC-1_1_1", "FAC-2_2_2", "FAC-2_2_3"]

    def test_document_id_es_alias_de_document_index(self):
        svc = TransferService()
        from app.models.document import split_documents

        doc = split_documents([{"is_separator": True, "separator_value": "A"}])[0]
        assert svc._build_filename("{document_id}", {}, {}, 1, doc) == "1"

    def test_un_campo_de_lote_no_pisa_las_variables(self):
        svc = TransferService()
        assert svc._build_filename("{batch_id}", {}, {"batch_id": "x"}, 5) == "5"

    def test_separator_sin_valor_bloquea(self, tmp_path):
        pages = _pages(tmp_path, [None, "A"])
        config = TransferConfig(
            destination=str(tmp_path / "out"), filename_pattern="{separator}"
        )
        problem = document_problems(pages, config)
        assert problem and "documento 1" in problem
        result = TransferService().transfer(pages, config)
        assert not result.success
        assert not (tmp_path / "out").exists()


class TestMultipage:
    def test_tiff_por_documento(self, tmp_path):
        pages = _pages(tmp_path, ["A", None, None, "B", None])
        config = TransferConfig(
            mode="tiff",
            grouping="document",
            destination=str(tmp_path / "out"),
            filename_pattern="{separator}",
            output_tiff_compression="group4",
        )
        result = TransferService().transfer(pages, config)
        assert result.success, result.errors
        assert result.files_transferred == 5
        assert _tiff_frames(tmp_path / "out" / "A.tif") == 3
        assert _tiff_frames(tmp_path / "out" / "B.tif") == 2
        with Image.open(tmp_path / "out" / "A.tif") as im:
            assert im.mode == "1"
            assert im.info.get("compression") == "group4"

    def test_sin_separadores_por_documento_es_por_lote(self, tmp_path):
        pages = _pages(tmp_path, [None, None])
        config = TransferConfig(
            mode="pdf",
            grouping="document",
            destination=str(tmp_path / "out"),
            filename_pattern="lote_{batch_id}",
        )
        result = TransferService().transfer(pages, config, batch_id=3)
        assert result.success, result.errors
        with pymupdf.open(tmp_path / "out" / "lote_3.pdf") as doc:
            assert doc.page_count == 2

    def test_pdf_por_lote(self, tmp_path):
        pages = _pages(tmp_path, ["A", None, "B"])
        config = TransferConfig(
            mode="pdf", destination=str(tmp_path / "out"), filename_pattern="todo"
        )
        result = TransferService().transfer(pages, config)
        assert result.success
        with pymupdf.open(tmp_path / "out" / "todo.pdf") as doc:
            assert doc.page_count == 3

    def test_merge_anexa_al_final_paginas_no_consecutivas(self, tmp_path):
        # Caso Arnau: cada página es separadora; el mismo código en dos
        # páginas no consecutivas acaba en el mismo TIFF.
        pages = _pages(tmp_path, ["111", "222", "111"])
        config = TransferConfig(
            mode="tiff",
            grouping="document",
            destination=str(tmp_path / "out"),
            filename_pattern="{separator}",
            collision_policy="merge",
        )
        assert TransferService().transfer(pages, config).success
        assert _tiff_frames(tmp_path / "out" / "111.tif") == 2
        assert _tiff_frames(tmp_path / "out" / "222.tif") == 1
        # Un segundo lote con el mismo código sigue creciendo por el final
        assert TransferService().transfer(_pages(tmp_path, ["111"]), config).success
        assert _tiff_frames(tmp_path / "out" / "111.tif") == 3

    def test_sin_merge_no_pisa(self, tmp_path):
        pages = _pages(tmp_path, ["111", "111"])
        config = TransferConfig(
            mode="tiff",
            grouping="document",
            destination=str(tmp_path / "out"),
            filename_pattern="{separator}",
        )
        assert TransferService().transfer(pages, config).success
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
            "111.tif",
            "111_1.tif",
        ]


class TestSeparatorPage:
    def test_exclude_descarta_la_hoja(self, tmp_path):
        pages = _pages(tmp_path, ["A", None, None, "B", None])
        config = TransferConfig(
            mode="tiff",
            grouping="document",
            separator_page="exclude",
            destination=str(tmp_path / "out"),
            filename_pattern="{separator}",
        )
        result = TransferService().transfer(pages, config)
        assert result.success, result.errors
        assert _tiff_frames(tmp_path / "out" / "A.tif") == 2
        assert _tiff_frames(tmp_path / "out" / "B.tif") == 1

    def test_exclude_en_modo_carpeta(self, tmp_path):
        pages = _pages(tmp_path, ["A", None])
        config = TransferConfig(
            destination=str(tmp_path / "out"),
            create_subdirs=False,
            separator_page="exclude",
            filename_pattern="{separator}_{page_index}",
        )
        assert TransferService().transfer(pages, config).success
        assert [p.stem for p in (tmp_path / "out").iterdir()] == ["A_1"]

    def test_documento_que_queda_vacio(self, tmp_path):
        pages = _pages(tmp_path, ["A", "B", None])
        config = TransferConfig(separator_page="exclude", destination="x")
        assert "solo tiene la hoja separadora" in document_problems(pages, config)

    def test_paginas_antes_de_la_primera_hoja(self, tmp_path):
        pages = _pages(tmp_path, [None, "A", None])
        config = TransferConfig(separator_page="exclude", destination="x")
        assert "antes de la primera hoja" in document_problems(pages, config)


ARNAU_LIKE = """
from datetime import datetime

def file_name(page, document, batch, app):
    codigo = document.separator_value
    if not codigo:
        raise ValueError(f"La página {page.page_index + 1} no tiene separador")
    codigo = codigo[-9:]
    fecha = datetime.strptime(batch.fields.get("Data") or "27/10/2026", "%d/%m/%Y")
    return f"{fecha:%Y%m%d}/{fecha.month}{fecha:%d}{codigo}"
"""


def _engine_with(script: str, config: TransferConfig) -> ScriptEngine:
    engine = ScriptEngine()
    compile_transfer_scripts(engine, config)
    return engine


class TestNameScript:
    def _config(self, tmp_path, script=ARNAU_LIKE) -> TransferConfig:
        return TransferConfig(
            mode="tiff",
            grouping="document",
            destination=str(tmp_path / "out"),
            name_mode="script",
            file_name_script=script,
            collision_policy="merge",
        )

    def test_subcarpeta_y_nombre_del_script(self, tmp_path):
        config = self._config(tmp_path)
        engine = _engine_with(ARNAU_LIKE, config)
        assert engine.is_compiled(FILE_NAME_SCRIPT_ID)
        result = execute_transfer(
            transfer_service=TransferService(),
            config=config,
            pages=_pages(tmp_path, ["1234567890", "55"]),
            batch_fields={"Data": "03/02/2026"},
            batch_id=1,
            contexts={"batch": BatchContext(fields={"Data": "03/02/2026"})},
            name_engine=engine,
        )
        assert result.success, result.errors
        out = tmp_path / "out" / "20260203"
        assert sorted(p.name for p in out.iterdir()) == [
            "203234567890.tif",
            "20355.tif",
        ]

    def test_si_el_script_lanza_no_se_escribe_nada(self, tmp_path):
        # La 2ª página abre un documento con nombre; la 1ª forma el
        # implícito, sin separador, y el script lanza con ella.
        config = self._config(tmp_path)
        result = execute_transfer(
            transfer_service=TransferService(),
            config=config,
            pages=_pages(tmp_path, [None, "111"]),
            batch_fields={},
            batch_id=1,
            contexts={"batch": BatchContext()},
            name_engine=_engine_with(ARNAU_LIKE, config),
        )
        assert not result.success
        assert "script de nombre" in result.errors[0]
        assert not (tmp_path / "out").exists()

    def test_devolver_none_usa_el_patron(self, tmp_path):
        script = "def file_name(page, document, batch, app):\n    return None\n"
        config = self._config(tmp_path, script)
        config.filename_pattern = "patron_{separator}"
        result = execute_transfer(
            transfer_service=TransferService(),
            config=config,
            pages=_pages(tmp_path, ["A"]),
            batch_fields={},
            batch_id=1,
            name_engine=_engine_with(script, config),
        )
        assert result.success, result.errors
        assert (tmp_path / "out" / "patron_A.tif").exists()

    def test_script_que_no_compila_bloquea(self, tmp_path):
        script = "def file_name(page:\n"
        config = self._config(tmp_path, script)
        result = execute_transfer(
            transfer_service=TransferService(),
            config=config,
            pages=_pages(tmp_path, ["A"]),
            batch_fields={},
            batch_id=1,
            name_engine=_engine_with(script, config),
        )
        assert not result.success
        assert "no está disponible" in result.errors[0]

    def test_el_script_no_saca_el_fichero_del_destino(self, tmp_path):
        script = (
            "def file_name(page, document, batch, app):\n    return '../../fuera'\n"
        )
        config = self._config(tmp_path, script)
        result = execute_transfer(
            transfer_service=TransferService(),
            config=config,
            pages=_pages(tmp_path, ["A"]),
            batch_fields={},
            batch_id=1,
            name_engine=_engine_with(script, config),
        )
        assert result.success, result.errors
        assert (tmp_path / "out" / "fuera.tif").exists()

    def test_name_mode_se_infiere_del_script(self):
        config = parse_transfer_config('{"file_name_script": "def file_name(): pass"}')
        assert config.name_mode == "script"
        assert parse_transfer_config("{}").name_mode == "pattern"


class TestValidateEvent:
    def test_el_evento_recibe_paginas_y_documentos(self, tmp_path):
        engine = ScriptEngine()
        engine.compile_script(
            "on_transfer_validate",
            (
                "def on_transfer_validate(app, batch, pages, documents):\n"
                "    sin = [p.page_index + 1 for p in pages if not p.is_separator]\n"
                "    if sin:\n"
                "        raise ValueError(f'Hi ha pàgines sense codi: la primera és la {sin[0]}')\n"
                "    return len(documents) == len(pages)\n"
            ),
        )
        ok = validate_before_transfer(
            script_engine=engine,
            contexts={"app": AppContext(), "batch": BatchContext()},
            fields_def=[],
            batch_fields={},
            pages=_pages(tmp_path, ["A", "B"]),
            config=TransferConfig(),
        )
        assert ok is None
        reason = validate_before_transfer(
            script_engine=engine,
            contexts={"app": AppContext(), "batch": BatchContext()},
            fields_def=[],
            batch_fields={},
            pages=_pages(tmp_path, ["A", None]),
            config=TransferConfig(),
        )
        assert "la primera és la 2" in reason

    def test_firma_antigua_sigue_funcionando(self, tmp_path):
        engine = ScriptEngine()
        engine.compile_script(
            "on_transfer_validate",
            "def on_transfer_validate(app, batch):\n    return True\n",
        )
        assert (
            validate_before_transfer(
                script_engine=engine,
                contexts={"app": AppContext(), "batch": BatchContext()},
                fields_def=[],
                batch_fields={},
                pages=_pages(tmp_path, ["A"]),
                config=TransferConfig(),
            )
            is None
        )


class TestNadaAMedias:
    """Revisión del lote 6: ningún fallo previsible deja salida parcial."""

    def test_imagen_ausente_no_escribe_nada_en_carpeta(self, tmp_path):
        pages = _pages(tmp_path, ["A", None])
        Path(pages[1]["image_path"]).unlink()
        config = TransferConfig(
            destination=str(tmp_path / "out"), filename_pattern="{page_index}"
        )
        result = TransferService().transfer(pages, config)
        assert not result.success
        assert "Faltan las imágenes de las páginas 2" in result.errors[0]
        assert not (tmp_path / "out").exists()

    def test_imagen_ausente_no_escribe_nada_en_multipagina(self, tmp_path):
        pages = _pages(tmp_path, ["A", "B"])
        Path(pages[1]["image_path"]).unlink()
        config = TransferConfig(
            mode="tiff",
            grouping="document",
            destination=str(tmp_path / "out"),
            filename_pattern="{separator}",
            collision_policy="merge",
        )
        assert not TransferService().transfer(pages, config).success
        assert not (tmp_path / "out").exists()

    def test_lote_sin_paginas_no_es_un_exito(self, tmp_path):
        config = TransferConfig(destination=str(tmp_path / "out"))
        result = TransferService().transfer([], config)
        assert not result.success

    def test_csv_no_se_bloquea_por_opciones_de_documento(self, tmp_path):
        reason = validate_before_transfer(
            script_engine=None,
            contexts={},
            fields_def=[],
            batch_fields={},
            pages=_pages(tmp_path, ["A"]),
            config=TransferConfig(mode="csv", separator_page="exclude"),
        )
        assert reason is None


class TestRechazoDeValidacion:
    """Un ValueError es un rechazo: aviso sin traza y solo el mensaje."""

    def _validar(self, tmp_path, cuerpo: str):
        engine = ScriptEngine()
        engine.compile_script(
            "on_transfer_validate",
            f"def on_transfer_validate(app, batch, pages):\n    {cuerpo}\n",
        )
        return validate_before_transfer(
            script_engine=engine,
            contexts={"app": AppContext(), "batch": BatchContext()},
            fields_def=[],
            batch_fields={},
            pages=_pages(tmp_path, ["A"]),
            config=TransferConfig(),
        )

    def test_value_error_es_un_rechazo_sin_traza(self, tmp_path, caplog):
        with caplog.at_level("INFO"):
            reason = self._validar(tmp_path, "raise ValueError('Falta el NHC')")
        assert reason == "Falta el NHC"
        assert not [r for r in caplog.records if r.levelname == "ERROR"]
        assert any(
            r.levelname == "WARNING" and "rechazado" in r.getMessage()
            for r in caplog.records
        )

    def test_otra_excepcion_es_un_fallo_con_traza(self, tmp_path, caplog):
        with caplog.at_level("INFO"):
            reason = self._validar(tmp_path, "return pages[0].no_existe")
        assert reason.startswith("Ha fallado la validación previa")
        assert "AttributeError" in reason
        assert any(r.levelname == "ERROR" and r.exc_info for r in caplog.records)


def test_el_log_nombra_el_fichero_final(tmp_path, caplog):
    pages = _pages(tmp_path, ["A"])
    config = TransferConfig(
        mode="tiff",
        grouping="document",
        destination=str(tmp_path / "out"),
        filename_pattern="{separator}",
    )
    with caplog.at_level("INFO"):
        assert TransferService().transfer(pages, config).success
    mensajes = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert not any(".tmp" in m for m in mensajes)
    assert any(m.endswith("A.tif: 1 página(s) escritas") for m in mensajes)
