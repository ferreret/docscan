"""Tests de la derivación de las tarjetas del launcher (paridad FlexibarNET10)."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.ui.launcher.app_card import (
    ACCENTS,
    ICONS,
    card_info,
    derive_icon_key,
    derive_tags,
    format_date,
    format_tag,
    pipeline_step_types,
    resolve_accent,
)
from app.ui.icons import available_icons


def _app(**kw):
    base = dict(
        id=1,
        name="Facturas",
        pipeline_json="[]",
        events_json="{}",
        transfer_json="{}",
        output_format="tiff",
        scanner_backend="",
        created_at=datetime(2026, 10, 1, 9, 30),
        updated_at=datetime(2026, 10, 26, 18, 0),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _pipeline(*types: str) -> str:
    return json.dumps([{"type": t, "id": f"s{i}"} for i, t in enumerate(types)])


def _fnv1a_utf16(text: str) -> int:
    """Implementación de referencia, independiente de la del módulo."""
    h = 2166136261
    units = []
    for ch in text:
        cp = ord(ch)
        if cp > 0xFFFF:  # par sustituto, como un string de .NET
            cp -= 0x10000
            units += [0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)]
        else:
            units.append(cp)
    for u in units:
        h = ((h ^ u) * 16777619) % 2**32
    return h


class TestCatalogo:
    def test_todos_los_iconos_estan_empaquetados(self):
        assert set(ICONS.values()) <= set(available_icons())

    def test_acentos_en_el_orden_de_flexibar(self):
        assert ACCENTS == ("blue", "green", "mauve", "peach", "yellow", "red", "orange")


class TestIcono:
    @pytest.mark.parametrize(
        ("kw", "esperado"),
        [
            ({"pipeline_json": _pipeline("ocr", "barcode")}, "barcode"),
            ({"pipeline_json": _pipeline("image_op", "ocr")}, "text"),
            ({"transfer_json": json.dumps({"mode": "pdf"})}, "pdf"),
            ({"transfer_json": json.dumps({"mode": "pdfa"})}, "pdf"),
            ({"transfer_json": json.dumps({"output_format": "pdf"})}, "pdf"),
            ({}, "document"),
        ],
    )
    def test_prioridad_barcode_ocr_pdf_documento(self, kw, esperado):
        assert derive_icon_key(_app(**kw)) == esperado

    def test_escaner_elegido_en_el_workbench(self):
        """Como DefaultScannerDeviceName de Flexibar: el escáner recordado."""
        from PySide6.QtCore import QSettings

        s = QSettings("DocScanStudio", "Workbench")
        s.setValue("source/77/scanner_name", "Canon DR-M160")
        try:
            assert derive_icon_key(_app(id=77)) == "scanner"
            # Con OCR, el OCR manda
            assert (
                derive_icon_key(_app(id=77, pipeline_json=_pipeline("ocr"))) == "text"
            )
        finally:
            s.remove("source/77")

    def test_el_backend_del_configurador_no_cuenta(self):
        """El Configurador siempre guarda un backend: no indica nada."""
        assert derive_icon_key(_app(id=78, scanner_backend="sane")) == "document"

    def test_json_roto_cae_a_documento(self):
        app = _app(pipeline_json="[no es json", transfer_json="{roto")
        assert derive_icon_key(app) == "document"
        assert card_info(app).icon_name == "file-text"


class TestAcento:
    @pytest.mark.parametrize(
        "nombre", ["Facturas", "Albaranes de entrada", "Ñandú", "Recetas 😀", ""]
    )
    def test_mismo_hash_que_flexibar(self, nombre):
        assert resolve_accent(nombre) == ACCENTS[_fnv1a_utf16(nombre) % len(ACCENTS)]

    def test_es_estable(self):
        assert resolve_accent("Facturas") == resolve_accent("Facturas")

    def test_nombres_distintos_dan_variedad(self):
        nombres = [f"Aplicación {i}" for i in range(30)]
        assert len({resolve_accent(n) for n in nombres}) >= 4


class TestEtiquetas:
    def test_maximo_tres(self):
        app = _app(
            pipeline_json=_pipeline("barcode", "ocr", "script"),
            transfer_json=json.dumps({"mode": "pdf", "destination": "/out"}),
        )
        assert derive_tags(app) == ("Códigos de barras", "OCR", "Scripts")

    def test_sin_nada_es_digitalizacion(self):
        assert derive_tags(_app()) == ("Digitalización",)

    def test_eventos_con_codigo_cuentan_como_scripts(self):
        app = _app(events_json=json.dumps({"on_app_start": "log.info('hola')"}))
        assert "Scripts" in derive_tags(app)

    def test_eventos_vacios_no_cuentan(self):
        app = _app(events_json=json.dumps({"on_app_start": "  "}))
        assert "Scripts" not in derive_tags(app)

    @pytest.mark.parametrize(
        ("transfer", "esperado"),
        [
            ({"mode": "pdf", "destination": "/out"}, "PDF"),
            ({"mode": "pdfa", "destination": "/out"}, "PDF/A"),
            ({"mode": "csv", "destination": "/out"}, "CSV"),
            ({"mode": "folder", "destination": "/out", "output_format": "png"}, "PNG"),
            ({"mode": "folder", "destination": "/out"}, "TIFF"),  # el de la App
            ({"mode": "pdf"}, None),  # sin destino
            ({"mode": "pdf", "destination": "/out", "standard_enabled": False}, None),
        ],
    )
    def test_formato_de_salida(self, transfer, esperado):
        assert format_tag(_app(transfer_json=json.dumps(transfer))) == esperado

    def test_pipeline_roto_no_lanza(self):
        assert pipeline_step_types("{no es una lista") == set()
        assert pipeline_step_types('{"type": "ocr"}') == set()


class TestFecha:
    def test_formato_de_flexibar(self):
        assert format_date(datetime(2026, 3, 7)) == "07/03/2026"

    def test_sin_fecha(self):
        assert format_date(None) == ""

    def test_usa_la_ultima_modificacion(self):
        assert card_info(_app()).updated == "26/10/2026"
        assert card_info(_app(updated_at=None)).updated == "01/10/2026"


class TestColorFijado:
    """Color del icono fijado en el Configurador (FlexibarNET10 IconAccent)."""

    def test_el_fijado_gana_al_automatico(self):
        assert card_info(_app(icon_accent="blue")).accent == "blue"

    def test_vacio_o_desconocido_es_automatico(self):
        auto = resolve_accent("Facturas")
        assert card_info(_app(icon_accent="")).accent == auto
        assert card_info(_app(icon_accent="fucsia")).accent == auto
        assert card_info(_app()).accent == auto  # App sin la columna
