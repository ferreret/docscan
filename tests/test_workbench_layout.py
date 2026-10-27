"""Tests del orden/visibilidad del panel derecho (app/models/workbench_layout.py)."""

from __future__ import annotations

import json

from app.models.workbench_layout import WorkbenchLayout


def ids(layout: WorkbenchLayout) -> list[str]:
    return [e.id for e in layout.entries]


def test_por_defecto_todo_visible_en_orden_historico():
    layout = WorkbenchLayout.from_json("")
    assert ids(layout) == ["barcodes", "campos", "verificacion", "ocr", "log"]
    assert layout.visible_tabs() == ["verificacion", "ocr", "log"]


def test_json_invalido_o_raro_usa_el_defecto():
    for raw in ("no es json", "{}", "[1, 2]", "null"):
        assert ids(WorkbenchLayout.from_json(raw)) == ids(WorkbenchLayout.default())


def test_ids_desconocidos_y_duplicados_se_ignoran_y_faltantes_se_anaden():
    layout = WorkbenchLayout.from_json(
        json.dumps(
            [
                {"id": "log", "visible": True},
                {"id": "inventada", "visible": True},
                {"id": "log", "visible": False},
            ]
        )
    )
    assert ids(layout) == ["barcodes", "campos", "log", "verificacion", "ocr"]
    assert layout.is_visible("log")


def test_paneles_siempre_primero_aunque_el_json_los_ponga_al_final():
    layout = WorkbenchLayout.from_json(
        json.dumps(
            [{"id": "ocr"}, {"id": "campos", "visible": False}, {"id": "barcodes"}]
        )
    )
    assert ids(layout)[:2] == ["barcodes", "campos"]
    assert not layout.is_visible("campos")


def test_ida_y_vuelta():
    layout = WorkbenchLayout.from_json(
        json.dumps([{"id": "log"}, {"id": "verificacion", "visible": False}])
    )
    assert WorkbenchLayout.from_json(layout.to_json()) == layout


def test_pestana_inicial():
    layout = WorkbenchLayout.from_json(
        json.dumps(
            [{"id": "verificacion", "visible": False}, {"id": "log"}, {"id": "ocr"}]
        )
    )
    assert layout.initial_tab("ocr") == "ocr"
    assert layout.initial_tab("verificacion") == "log"  # oculta: primera visible
    assert layout.initial_tab("lote") == "log"  # valor antiguo
    assert layout.initial_tab("") == "log"
    sin_pestanas = WorkbenchLayout.from_json(
        json.dumps(
            [{"id": t, "visible": False} for t in ("verificacion", "ocr", "log")]
        )
    )
    assert sin_pestanas.initial_tab("ocr") is None
