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
from app.models.operation_history import OperationHistory
from app.db.repositories.application_repo import ApplicationRepository
from app.db.repositories.batch_repo import BatchRepository
from app.db.repositories.page_repo import PageRepository
from app.db.repositories.operation_history_repo import OperationHistoryRepository


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


# ------------------------------------------------------------------
# PageRepository
# ------------------------------------------------------------------


class TestPageRepository:
    def _make_batch(self, session: Session) -> Batch:
        """Crea una Application + Batch de apoyo y devuelve el Batch."""
        app = Application(name=f"PageRepoApp_{id(session)}")
        batch = Batch(application=app, state="created")
        session.add(app)
        session.flush()
        return batch

    def test_save_and_get_by_id(self, session):
        """save persiste la página y get_by_id la recupera por PK."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        page = Page(batch=batch, page_index=0, image_path="/tmp/p0.tiff")
        saved = repo.save(page)

        assert saved.id is not None
        retrieved = repo.get_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.page_index == 0
        assert retrieved.image_path == "/tmp/p0.tiff"

    def test_get_by_id_inexistente_retorna_none(self, session):
        """get_by_id con PK inexistente devuelve None."""
        repo = PageRepository(session)
        assert repo.get_by_id(999999) is None

    def test_get_by_batch_ordenado_por_indice(self, session):
        """get_by_batch devuelve las páginas ordenadas por page_index."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        repo.save_all([
            Page(batch=batch, page_index=2, image_path="/tmp/p2.tiff"),
            Page(batch=batch, page_index=0, image_path="/tmp/p0.tiff"),
            Page(batch=batch, page_index=1, image_path="/tmp/p1.tiff"),
        ])

        pages = repo.get_by_batch(batch.id)
        assert len(pages) == 3
        assert [p.page_index for p in pages] == [0, 1, 2]

    def test_get_by_batch_sin_paginas_retorna_lista_vacia(self, session):
        """get_by_batch sobre un lote sin páginas devuelve lista vacía."""
        batch = self._make_batch(session)
        repo = PageRepository(session)
        assert repo.get_by_batch(batch.id) == []

    def test_get_by_batch_no_mezcla_lotes(self, session):
        """get_by_batch filtra solo las páginas del lote indicado."""
        app = Application(name="MultiLoteApp")
        batch_a = Batch(application=app, state="created")
        batch_b = Batch(application=app, state="created")
        session.add(app)
        session.flush()

        repo = PageRepository(session)
        repo.save(Page(batch=batch_a, page_index=0))
        repo.save(Page(batch=batch_b, page_index=0))
        repo.save(Page(batch=batch_b, page_index=1))

        assert len(repo.get_by_batch(batch_a.id)) == 1
        assert len(repo.get_by_batch(batch_b.id)) == 2

    def test_save_all_persiste_multiples_paginas(self, session):
        """save_all inserta varias páginas en una sola llamada."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        pages = [Page(batch=batch, page_index=i) for i in range(5)]
        resultado = repo.save_all(pages)

        assert len(resultado) == 5
        assert all(p.id is not None for p in resultado)

    def test_get_needs_review_filtra_correctamente(self, session):
        """get_needs_review solo devuelve páginas con needs_review=True."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        repo.save(Page(batch=batch, page_index=0, needs_review=False))
        repo.save(Page(batch=batch, page_index=1, needs_review=True, review_reason="Barcode ilegible"))
        repo.save(Page(batch=batch, page_index=2, needs_review=True, review_reason="OCR bajo"))
        repo.save(Page(batch=batch, page_index=3, needs_review=False))

        needs_review = repo.get_needs_review(batch.id)
        assert len(needs_review) == 2
        assert all(p.needs_review for p in needs_review)
        assert [p.page_index for p in needs_review] == [1, 2]

    def test_get_needs_review_sin_candidatos_retorna_vacio(self, session):
        """get_needs_review devuelve lista vacía si ninguna página necesita revisión."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        repo.save_all([
            Page(batch=batch, page_index=i, needs_review=False) for i in range(3)
        ])

        assert repo.get_needs_review(batch.id) == []

    def test_delete_elimina_pagina(self, session):
        """delete borra la página y get_by_id devuelve None."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        page = repo.save(Page(batch=batch, page_index=0))
        page_id = page.id

        repo.delete(page_id)
        assert repo.get_by_id(page_id) is None

    def test_delete_id_inexistente_no_lanza_excepcion(self, session):
        """delete con PK inexistente no lanza ninguna excepción."""
        repo = PageRepository(session)
        repo.delete(999999)  # no debe propagar error

    def test_count_by_batch_retorna_total_correcto(self, session):
        """count_by_batch devuelve el número exacto de páginas del lote."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        assert repo.count_by_batch(batch.id) == 0

        repo.save_all([Page(batch=batch, page_index=i) for i in range(4)])
        assert repo.count_by_batch(batch.id) == 4

    def test_count_by_batch_no_cuenta_otras_paginas(self, session):
        """count_by_batch no incluye páginas de otros lotes."""
        app = Application(name="CountApp")
        batch_a = Batch(application=app, state="created")
        batch_b = Batch(application=app, state="created")
        session.add(app)
        session.flush()

        repo = PageRepository(session)
        repo.save_all([Page(batch=batch_a, page_index=i) for i in range(3)])
        repo.save(Page(batch=batch_b, page_index=0))

        assert repo.count_by_batch(batch_a.id) == 3
        assert repo.count_by_batch(batch_b.id) == 1

    def test_save_actualiza_campos_opcionales(self, session):
        """save persiste correctamente los campos opcionales de Page."""
        batch = self._make_batch(session)
        repo = PageRepository(session)

        page = Page(
            batch=batch,
            page_index=0,
            image_path="/tmp/scan.tiff",
            ocr_text="Texto reconocido",
            is_blank=False,
            is_excluded=False,
            needs_review=True,
            review_reason="Baja confianza OCR",
        )
        repo.save(page)

        recovered = repo.get_by_id(page.id)
        assert recovered.ocr_text == "Texto reconocido"
        assert recovered.needs_review is True
        assert recovered.review_reason == "Baja confianza OCR"
        assert recovered.is_blank is False


# ------------------------------------------------------------------
# OperationHistoryRepository
# ------------------------------------------------------------------


class TestOperationHistoryRepository:
    def _make_batch(self, session: Session, app_name: str = "HistApp") -> Batch:
        """Crea una Application + Batch de apoyo y devuelve el Batch."""
        app = Application(name=app_name)
        batch = Batch(application=app, state="created")
        session.add(app)
        session.flush()
        return batch

    def test_add_persiste_entrada(self, session):
        """add inserta una entrada y asigna id."""
        batch = self._make_batch(session)
        repo = OperationHistoryRepository(session)

        entry = OperationHistory(
            batch_id=batch.id,
            operation="state_change",
            old_state="created",
            new_state="read",
            username="tester",
            message="Lote leído correctamente",
        )
        saved = repo.add(entry)

        assert saved.id is not None
        assert saved.batch_id == batch.id

    def test_get_by_batch_retorna_entradas_del_lote(self, session):
        """get_by_batch devuelve solo las entradas del lote indicado."""
        batch = self._make_batch(session, "HistApp2")
        repo = OperationHistoryRepository(session)

        repo.add(OperationHistory(batch_id=batch.id, operation="state_change", old_state="created", new_state="read"))
        repo.add(OperationHistory(batch_id=batch.id, operation="export", old_state="read", new_state="exported"))

        entries = repo.get_by_batch(batch.id)
        assert len(entries) == 2
        assert all(e.batch_id == batch.id for e in entries)

    def test_get_by_batch_sin_entradas_retorna_lista_vacia(self, session):
        """get_by_batch sobre un lote sin historial devuelve lista vacía."""
        batch = self._make_batch(session, "HistApp3")
        repo = OperationHistoryRepository(session)
        assert repo.get_by_batch(batch.id) == []

    def test_get_by_batch_no_mezcla_lotes(self, session):
        """get_by_batch no devuelve entradas de otros lotes."""
        app = Application(name="HistMultiApp")
        batch_a = Batch(application=app, state="created")
        batch_b = Batch(application=app, state="created")
        session.add(app)
        session.flush()

        repo = OperationHistoryRepository(session)
        repo.add(OperationHistory(batch_id=batch_a.id, operation="op_a1"))
        repo.add(OperationHistory(batch_id=batch_a.id, operation="op_a2"))
        repo.add(OperationHistory(batch_id=batch_b.id, operation="op_b1"))

        assert len(repo.get_by_batch(batch_a.id)) == 2
        assert len(repo.get_by_batch(batch_b.id)) == 1

    def test_get_by_batch_orden_descendente_por_timestamp(self, session):
        """get_by_batch devuelve las entradas en orden descendente (más reciente primero)."""
        from datetime import datetime, timedelta

        batch = self._make_batch(session, "HistOrderApp")
        repo = OperationHistoryRepository(session)

        base = datetime(2026, 3, 1, 10, 0, 0)
        e1 = OperationHistory(batch_id=batch.id, operation="op_primera", timestamp=base)
        e2 = OperationHistory(batch_id=batch.id, operation="op_segunda", timestamp=base + timedelta(hours=1))
        e3 = OperationHistory(batch_id=batch.id, operation="op_tercera", timestamp=base + timedelta(hours=2))

        repo.add(e1)
        repo.add(e2)
        repo.add(e3)

        entries = repo.get_by_batch(batch.id)
        assert entries[0].operation == "op_tercera"
        assert entries[1].operation == "op_segunda"
        assert entries[2].operation == "op_primera"

    def test_add_persiste_campos_opcionales(self, session):
        """add guarda correctamente todos los campos de OperationHistory."""
        batch = self._make_batch(session, "HistFieldsApp")
        repo = OperationHistoryRepository(session)

        entry = repo.add(OperationHistory(
            batch_id=batch.id,
            operation="error",
            old_state="read",
            new_state="error_read",
            username="supervisor",
            message="Fallo en paso barcode: código ilegible",
        ))

        recovered = session.get(OperationHistory, entry.id)
        assert recovered.operation == "error"
        assert recovered.old_state == "read"
        assert recovered.new_state == "error_read"
        assert recovered.username == "supervisor"
        assert recovered.message == "Fallo en paso barcode: código ilegible"

    def test_cascade_delete_al_borrar_lote(self, session):
        """Al eliminar un lote su historial se borra en cascada."""
        batch = self._make_batch(session, "HistCascadeApp")
        repo = OperationHistoryRepository(session)

        entry = repo.add(OperationHistory(batch_id=batch.id, operation="state_change"))
        entry_id = entry.id

        session.delete(batch)
        session.flush()

        assert session.get(OperationHistory, entry_id) is None

    def test_add_multiples_operaciones_mismo_lote(self, session):
        """Se pueden registrar múltiples operaciones para el mismo lote."""
        batch = self._make_batch(session, "HistMultiOpApp")
        repo = OperationHistoryRepository(session)

        operaciones = ["state_change", "export", "reopen", "state_change", "export"]
        for op in operaciones:
            repo.add(OperationHistory(batch_id=batch.id, operation=op))

        entries = repo.get_by_batch(batch.id)
        assert len(entries) == len(operaciones)
