"""Tests de base de datos, modelos ORM y repositorios."""

import sqlite3

import pytest
from sqlalchemy.orm import Session

from app.db.database import create_db_engine, create_tables, get_session_factory, Base
from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.models.barcode import Barcode
from app.models.template import Template
from app.db.repositories.application_repo import ApplicationRepository
from app.db.repositories.batch_repo import BatchRepository


@pytest.fixture
def db_engine(tmp_path):
    """Engine SQLite temporal con tablas creadas."""
    engine = create_db_engine(tmp_path / "test.db")
    create_tables(engine)
    return engine


@pytest.fixture
def session(db_engine):
    """Session con rollback automático al finalizar."""
    factory = get_session_factory(db_engine)
    with factory() as session:
        with session.begin():
            yield session


# ------------------------------------------------------------------
# WAL mode
# ------------------------------------------------------------------


class TestWalMode:
    def test_wal_mode_enabled(self, db_engine, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db_engine):
        with db_engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1


# ------------------------------------------------------------------
# Modelos ORM
# ------------------------------------------------------------------


class TestModels:
    def test_create_application(self, session):
        app = Application(name="Test App", description="Desc")
        session.add(app)
        session.flush()
        assert app.id is not None

    def test_application_batch_relationship(self, session):
        app = Application(name="App1")
        batch = Batch(application=app, state="created")
        session.add(app)
        session.flush()
        assert len(app.batches) == 1
        assert app.batches[0].state == "created"

    def test_batch_page_relationship(self, session):
        app = Application(name="App2")
        batch = Batch(application=app, state="created")
        page = Page(batch=batch, page_index=0, image_path="/tmp/img.tiff")
        session.add(app)
        session.flush()
        assert len(batch.pages) == 1
        assert batch.pages[0].page_index == 0

    def test_page_barcode_relationship(self, session):
        app = Application(name="App3")
        batch = Batch(application=app, state="created")
        page = Page(batch=batch, page_index=0)
        bc = Barcode(
            page=page,
            value="12345678",
            symbology="Code128",
            engine="motor1",
            step_id="s1",
        )
        session.add(app)
        session.flush()
        assert len(page.barcodes) == 1
        assert page.barcodes[0].value == "12345678"
        assert page.barcodes[0].role == ""

    def test_application_template_relationship(self, session):
        app = Application(name="App4")
        tpl = Template(
            application=app,
            name="Factura",
            provider="anthropic",
            prompt="Extrae los campos...",
        )
        session.add(app)
        session.flush()
        assert len(app.templates) == 1

    def test_cascade_delete(self, session):
        app = Application(name="App5")
        batch = Batch(application=app, state="created")
        page = Page(batch=batch, page_index=0)
        Barcode(
            page=page, value="X", symbology="QR",
            engine="motor2", step_id="s1",
        )
        session.add(app)
        session.flush()

        session.delete(app)
        session.flush()
        # Todo se borra en cascada
        assert session.get(Batch, batch.id) is None


# ------------------------------------------------------------------
# Repositorios
# ------------------------------------------------------------------


class TestApplicationRepository:
    def test_save_and_get(self, session):
        repo = ApplicationRepository(session)
        app = Application(name="Repo Test")
        repo.save(app)
        assert repo.get_by_id(app.id) is not None

    def test_get_by_name(self, session):
        repo = ApplicationRepository(session)
        repo.save(Application(name="FindMe"))
        assert repo.get_by_name("FindMe") is not None
        assert repo.get_by_name("NotFound") is None

    def test_get_all_active(self, session):
        repo = ApplicationRepository(session)
        repo.save(Application(name="Active", active=True))
        repo.save(Application(name="Inactive", active=False))
        actives = repo.get_all_active()
        assert len(actives) == 1
        assert actives[0].name == "Active"

    def test_delete(self, session):
        repo = ApplicationRepository(session)
        app = Application(name="ToDelete")
        repo.save(app)
        app_id = app.id
        repo.delete(app_id)
        assert repo.get_by_id(app_id) is None


class TestBatchRepository:
    def test_save_and_get(self, session):
        app = Application(name="BatchApp")
        session.add(app)
        session.flush()

        repo = BatchRepository(session)
        batch = Batch(application_id=app.id, state="created")
        repo.save(batch)
        assert repo.get_by_id(batch.id) is not None

    def test_get_by_state(self, session):
        app = Application(name="StateApp")
        session.add(app)
        session.flush()

        repo = BatchRepository(session)
        repo.save(Batch(application_id=app.id, state="created"))
        repo.save(Batch(application_id=app.id, state="exported"))

        created = repo.get_by_state("created")
        assert len(created) == 1
