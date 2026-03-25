"""Tests del servicio de exportacion/importacion de aplicaciones."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.services.app_export_service import (
    EXPORT_VERSION,
    AppImportError,
    export_application,
    export_to_file,
    import_application,
    validate_import_data,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as sess:
        yield sess


@pytest.fixture
def sample_app(session: Session) -> Application:
    """Crea una aplicacion de ejemplo en BD."""
    app = Application(
        name="Facturas",
        description="App de facturas",
        active=True,
        pipeline_json=json.dumps([
            {"id": "s1", "type": "image_op", "op": "AutoDeskew"},
            {"id": "s2", "type": "barcode", "engine": "motor1", "symbologies": ["Code128"]},
        ]),
        events_json=json.dumps({"on_app_start": "log.info('Inicio')"}),
        transfer_json=json.dumps({"mode": "folder", "destination": "/tmp/export"}),
        batch_fields_json=json.dumps([{"label": "Ref", "type": "texto"}]),
        index_fields_json=json.dumps([]),
        image_config_json=json.dumps({"format": "tiff", "compression": "lzw"}),
        ai_config_json=json.dumps({"barcode_regex": "^[A-Z]\\d{8}$"}),
        auto_transfer=False,
        close_after_transfer=True,
        background_color="#1e1e2e",
        output_format="tiff",
        default_tab="lote",
        scanner_backend="sane",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------
# Tests de export
# ---------------------------------------------------------------

class TestExport:
    def test_export_contains_all_fields(self, sample_app):
        data = export_application(sample_app)
        app_data = data["application"]
        assert app_data["name"] == "Facturas"
        assert app_data["description"] == "App de facturas"
        assert app_data["active"] is True
        assert app_data["auto_transfer"] is False
        assert app_data["close_after_transfer"] is True
        assert app_data["background_color"] == "#1e1e2e"
        assert app_data["output_format"] == "tiff"
        assert app_data["default_tab"] == "lote"
        assert app_data["scanner_backend"] == "sane"

    def test_export_excludes_db_fields(self, sample_app):
        data = export_application(sample_app)
        app_data = data["application"]
        assert "id" not in app_data
        assert "created_at" not in app_data
        assert "updated_at" not in app_data

    def test_export_version_and_metadata(self, sample_app):
        data = export_application(sample_app)
        assert data["version"] == EXPORT_VERSION
        assert "exported_at" in data

    def test_json_fields_are_parsed(self, sample_app):
        data = export_application(sample_app)
        app_data = data["application"]
        # pipeline_json debe ser una lista, no un string
        assert isinstance(app_data["pipeline_json"], list)
        assert len(app_data["pipeline_json"]) == 2
        # events_json debe ser un dict
        assert isinstance(app_data["events_json"], dict)
        assert "on_app_start" in app_data["events_json"]
        # transfer_json debe ser un dict
        assert isinstance(app_data["transfer_json"], dict)
        # ai_config_json debe ser un dict
        assert isinstance(app_data["ai_config_json"], dict)

    def test_export_to_file(self, sample_app, tmp_path):
        filepath = tmp_path / "test.docscan"
        export_to_file(sample_app, filepath)
        assert filepath.exists()
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["version"] == EXPORT_VERSION
        assert data["application"]["name"] == "Facturas"


# ---------------------------------------------------------------
# Tests de validacion
# ---------------------------------------------------------------

class TestValidation:
    def test_valid_data(self, sample_app):
        data = export_application(sample_app)
        errors = validate_import_data(data)
        assert errors == []

    def test_missing_version(self):
        data = {"application": {"name": "Test"}}
        errors = validate_import_data(data)
        assert any("version" in e.lower() for e in errors)

    def test_unsupported_version(self):
        data = {"version": 999, "application": {"name": "Test"}}
        errors = validate_import_data(data)
        assert any("no soportada" in e.lower() for e in errors)

    def test_missing_application(self):
        data = {"version": 1}
        errors = validate_import_data(data)
        assert any("application" in e.lower() for e in errors)

    def test_missing_name(self):
        data = {"version": 1, "application": {}}
        errors = validate_import_data(data)
        assert any("nombre" in e.lower() for e in errors)

    def test_not_a_dict(self):
        errors = validate_import_data("invalid")
        assert len(errors) > 0


# ---------------------------------------------------------------
# Tests de import
# ---------------------------------------------------------------

class TestImport:
    def test_import_creates_app(self, session):
        data = {
            "version": 1,
            "application": {
                "name": "Nueva App",
                "description": "Importada",
                "pipeline_json": [{"id": "s1", "type": "image_op", "op": "FxGrayscale"}],
                "auto_transfer": True,
            },
        }
        app = import_application(data, session)
        session.commit()
        assert app.name == "Nueva App"
        assert app.description == "Importada"
        assert app.auto_transfer is True
        assert '"FxGrayscale"' in app.pipeline_json

    def test_import_name_collision_auto_suffix(self, session, sample_app):
        data = export_application(sample_app)
        app = import_application(data, session)
        session.commit()
        assert app.name == "Facturas (importada)"

    def test_import_name_override(self, session):
        data = {
            "version": 1,
            "application": {"name": "Original"},
        }
        app = import_application(data, session, name_override="Renombrada")
        session.commit()
        assert app.name == "Renombrada"

    def test_import_invalid_data_raises(self, session):
        with pytest.raises(AppImportError):
            import_application({"invalid": True}, session)

    def test_double_collision_increments(self, session, sample_app):
        data = export_application(sample_app)
        # Primera importacion
        app1 = import_application(data, session)
        session.commit()
        assert app1.name == "Facturas (importada)"
        # Segunda importacion
        app2 = import_application(data, session)
        session.commit()
        assert app2.name == "Facturas (importada 2)"


# ---------------------------------------------------------------
# Test roundtrip
# ---------------------------------------------------------------

class TestRoundtrip:
    def test_export_import_preserves_all_fields(self, session, sample_app):
        data = export_application(sample_app)
        imported = import_application(data, session, name_override="Facturas Clone")
        session.commit()

        assert imported.description == sample_app.description
        assert imported.active == sample_app.active
        assert imported.pipeline_json == sample_app.pipeline_json
        assert imported.events_json == sample_app.events_json
        assert imported.transfer_json == sample_app.transfer_json
        assert imported.batch_fields_json == sample_app.batch_fields_json
        assert imported.index_fields_json == sample_app.index_fields_json
        assert imported.image_config_json == sample_app.image_config_json
        assert imported.ai_config_json == sample_app.ai_config_json
        assert imported.auto_transfer == sample_app.auto_transfer
        assert imported.close_after_transfer == sample_app.close_after_transfer
        assert imported.background_color == sample_app.background_color
        assert imported.output_format == sample_app.output_format
        assert imported.default_tab == sample_app.default_tab
        assert imported.scanner_backend == sample_app.scanner_backend

    def test_file_roundtrip(self, session, sample_app, tmp_path):
        filepath = tmp_path / "roundtrip.docscan"
        export_to_file(sample_app, filepath)
        data = json.loads(filepath.read_text(encoding="utf-8"))
        imported = import_application(data, session, name_override="Roundtrip")
        session.commit()
        assert imported.pipeline_json == sample_app.pipeline_json
