"""Smoke de extremo a extremo con las Apps de archivo del Arnau (lote 6).

Es la prueba de aceptación del separador de documento: las seis Apps de la
familia A, portadas de FlexibarNET10 (``tools/arnau_apps.py``), procesan
páginas sintéticas con códigos de barras reales por el camino del worker
desatendido (importar → pipeline con lectura real → validación →
transferencia). Nada de mocks en medio: si la lectura, la detección del
separador, el script de nombre o el TIFF Group4 fallan, falla aquí.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("zxingcpp")


def _load_tool(name: str):
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_tool("seed_apps_arnau")

DATA = "27/10/2026"


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    base = tmp_path_factory.mktemp("arnau")
    paginas = seed.generar_paginas(base / "paginas")
    db = base / "arnau.db"
    seed.sembrar(db, str(base / "salida"))
    return {
        "base": base,
        "db": db,
        "salida": base / "salida",
        "paginas": {p.name[:2]: p for p in paginas},
    }


def _procesar(entorno, app_name: str, hojas: list[str], data: str = DATA):
    """Importa las hojas en un lote nuevo, lo procesa y lo transfiere.

    Returns:
        (estado final del lote, lote)
    """
    from app.db.database import create_db_engine, get_session_factory
    from app.models.application import Application
    from app.models.batch import Batch
    from app.services.batch_service import BatchService
    from app.services.import_service import ImportService
    from app.services.notification_service import NotificationService
    from app.services.script_engine import ScriptEngine
    from app.services.transfer_flow import compile_transfer_scripts
    from app.services.transfer_service import TransferService, parse_transfer_config
    from app.workers.recognition_worker import AppContext, BatchContext
    from docscan_worker import worker_main as wm

    engine = create_db_engine(db_path=entorno["db"])
    session_factory = get_session_factory(engine)
    images_dir = entorno["base"] / "images"
    with session_factory() as s:
        app_record = s.query(Application).filter(Application.name == app_name).one()
        s.expunge(app_record)

    script_engine = ScriptEngine()
    lifecycle = wm._compile_lifecycle_events(app_record, script_engine)
    compile_transfer_scripts(
        script_engine, parse_transfer_config(app_record.transfer_json)
    )
    executor = wm._build_executor(app_record, script_engine)

    wm._process_files(
        [entorno["paginas"][h] for h in hojas],
        app_record,
        executor,
        ImportService(),
        script_engine,
        lifecycle,
        session_factory,
        images_dir,
    )
    with session_factory() as s:
        batch = s.query(Batch).order_by(Batch.id.desc()).first()
        svc = BatchService(s, images_dir)
        svc.set_fields(batch.id, {"Data": data})
        s.commit()
        wm._transfer_batch(
            batch.id,
            app_record,
            svc,
            TransferService(),
            NotificationService(),
            script_engine,
            lifecycle,
            s,
            AppContext(id=app_record.id, name=app_record.name),
            BatchContext(id=batch.id, state=batch.state),
        )
        s.refresh(batch)
        state = batch.state
        pages = [(p.is_separator, p.separator_value) for p in svc.get_pages(batch.id)]
    engine.dispose()
    return state, pages


def _frames(path: Path) -> int:
    with Image.open(path) as im:
        assert im.mode == "1"
        assert im.info.get("compression") == "group4"
        return getattr(im, "n_frames", 1)


def test_los_packs_se_siembran_con_scripts_que_compilan(entorno):
    from app.db.database import create_db_engine, get_session_factory
    from app.models.application import Application

    engine = create_db_engine(db_path=entorno["db"])
    with get_session_factory(engine)() as s:
        names = sorted(a.name for a in s.query(Application).all())
        app = s.query(Application).filter(Application.name.like("01%")).one()
        transfer = json.loads(app.transfer_json)
    engine.dispose()
    assert len(names) == 6
    assert transfer["mode"] == "tiff"
    assert transfer["grouping"] == "document"
    assert transfer["collision_policy"] == "merge"
    assert transfer["name_mode"] == "script"
    # Sembrar dos veces no duplica (upsert por nombre)
    seed.sembrar(entorno["db"], str(entorno["salida"]))
    engine = create_db_engine(db_path=entorno["db"])
    with get_session_factory(engine)() as s:
        assert s.query(Application).count() == 6
    engine.dispose()


def test_01_un_tiff_por_codigo_y_el_repetido_se_anexa(entorno):
    state, pages = _procesar(entorno, "01 Arxiu de Peticions", ["01", "02", "03"])
    assert state == "exported"
    assert pages == [(True, "12345678"), (True, "12345678"), (True, "0812345678")]
    dia = entorno["salida"] / "20261027"
    assert _frames(dia / "12345678.tif") == 2
    assert _frames(dia / "0812345678.tif") == 1


def test_01_una_pagina_sin_codigo_bloquea_sin_escribir(entorno):
    antes = sorted((entorno["salida"]).rglob("*.tif"))
    state, pages = _procesar(entorno, "01 Arxiu de Peticions", ["01", "04"])
    assert state == "error_export"  # bloqueado: no se exporta
    assert pages[1] == (False, "")
    assert sorted((entorno["salida"]).rglob("*.tif")) == antes


def test_01_code39_no_es_separador(entorno):
    state, pages = _procesar(entorno, "01 Arxiu de Peticions", ["05"])
    assert state == "error_export"
    assert pages == [(False, "")]


def test_02_subcarpeta_y_anexado_entre_lotes(entorno):
    for _ in range(2):
        state, _pages = _procesar(entorno, "02 Documents de Qualitat", ["01"])
        assert state == "exported"
    assert _frames(entorno["salida"] / "Qualitat" / "20261027" / "12345678.tif") == 2


def test_03_micro_antepone_mes_y_dia(entorno):
    state, _pages = _procesar(entorno, "03 Resultats de Micro", ["01"], "05/03/2026")
    assert state == "exported"
    assert (entorno["salida"] / "MR-MICRO" / "20260305" / "30512345678.tif").exists()


def test_05_diez_digitos_se_archiva_por_los_nueve_ultimos(entorno):
    state, _pages = _procesar(entorno, "05 Arxiu de Peticions 10 DIGITS", ["03"])
    assert state == "exported"
    assert (entorno["salida"] / "20261027" / "812345678.tif").exists()


def test_05_solo_lee_itf(entorno):
    # Code128 no está entre sus simbologías: la página queda sin separador
    state, pages = _procesar(entorno, "05 Arxiu de Peticions 10 DIGITS", ["01"])
    assert state == "error_export"
    assert pages == [(False, "")]


def test_07_micro_diez_digitos(entorno):
    state, _pages = _procesar(entorno, "07 Resultats de Micro 10 DIGITS", ["03"])
    assert state == "exported"
    assert (entorno["salida"] / "MR-MICRO" / "20261027" / "1027812345678.tif").exists()


def test_el_workbench_compila_el_script_de_nombre(entorno, qtbot, tmp_path):
    from unittest.mock import patch

    from app.db.database import create_db_engine, get_session_factory
    from app.models.application import Application
    from app.services.transfer_flow import FILE_NAME_SCRIPT_ID
    from app.ui.workbench.workbench_window import WorkbenchWindow

    engine = create_db_engine(db_path=entorno["db"])
    session_factory = get_session_factory(engine)
    with session_factory() as s:
        app_id = s.query(Application).filter(Application.name.like("01%")).one().id
    with patch("app.ui.workbench.workbench_window.APP_DATA_DIR", tmp_path):
        window = WorkbenchWindow(app_id=app_id, session_factory=session_factory)
    qtbot.addWidget(window)
    assert window._script_engine.is_compiled(FILE_NAME_SCRIPT_ID)
    assert window._separator_step().separator_regex == "^(02|10)"
    window.close()
    engine.dispose()
