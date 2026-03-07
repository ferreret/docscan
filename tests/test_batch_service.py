"""Tests del servicio de lotes."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.services.batch_service import BatchService


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
def app_id(session: Session) -> int:
    app = Application(name="Test App")
    session.add(app)
    session.commit()
    return app.id


@pytest.fixture
def service(session: Session, tmp_path: Path) -> BatchService:
    return BatchService(session=session, images_dir=tmp_path)


@pytest.fixture
def sample_images() -> list[np.ndarray]:
    return [
        np.zeros((100, 200, 3), dtype=np.uint8),
        np.ones((100, 200, 3), dtype=np.uint8) * 128,
        np.ones((100, 200, 3), dtype=np.uint8) * 255,
    ]


# ------------------------------------------------------------------
# Creación de lotes
# ------------------------------------------------------------------


class TestCreateBatch:
    def test_create_basic(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        assert batch.id is not None
        assert batch.state == "created"
        assert batch.application_id == app_id

    def test_create_with_fields(self, service: BatchService, app_id: int):
        batch = service.create_batch(
            app_id, fields={"cliente": "ACME", "tipo": "factura"},
        )
        fields = json.loads(batch.fields_json)
        assert fields["cliente"] == "ACME"

    def test_create_records_hostname(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        assert batch.hostname != ""
        assert batch.username != ""


# ------------------------------------------------------------------
# Páginas
# ------------------------------------------------------------------


class TestPages:
    def test_add_pages(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images)
        assert len(pages) == 3
        assert all(p.page_index == i for i, p in enumerate(pages))
        # Imágenes deben existir en disco
        for p in pages:
            assert Path(p.image_path).exists()

    def test_add_pages_increments_count(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        service.add_pages(batch.id, sample_images[:2])
        service.add_pages(batch.id, sample_images[2:])
        assert batch.page_count == 3

    def test_add_pages_continues_index(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        service.add_pages(batch.id, sample_images[:2])
        pages2 = service.add_pages(batch.id, sample_images[2:])
        assert pages2[0].page_index == 2

    def test_get_page_image(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images[:1])
        img = service.get_page_image(pages[0])
        assert img is not None
        assert img.shape == (100, 200, 3)

    def test_remove_page(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray], session: Session,
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images[:1])
        image_path = Path(pages[0].image_path)
        assert image_path.exists()

        service.remove_page(pages[0].id)
        assert not image_path.exists()

    def test_reorder_pages(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images)
        # Invertir orden
        new_order = [pages[2].id, pages[1].id, pages[0].id]
        service.reorder_pages(batch.id, new_order)

        reloaded = service.get_pages(batch.id)
        assert reloaded[0].id == pages[2].id
        assert reloaded[0].page_index == 0

    def test_add_pages_invalid_batch(self, service: BatchService):
        with pytest.raises(ValueError, match="no encontrado"):
            service.add_pages(9999, [np.zeros((10, 10, 3), dtype=np.uint8)])


# ------------------------------------------------------------------
# Estado
# ------------------------------------------------------------------


class TestState:
    def test_transition_state(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        updated = service.transition_state(batch.id, "read")
        assert updated.state == "read"

    def test_transition_state_invalid(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        with pytest.raises(ValueError, match="no válido"):
            service.transition_state(batch.id, "invalid_state")

    def test_transition_state_nonexistent(self, service: BatchService):
        with pytest.raises(ValueError, match="no encontrado"):
            service.transition_state(9999, "read")


# ------------------------------------------------------------------
# Consultas
# ------------------------------------------------------------------


class TestQueries:
    def test_get_batch(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        found = service.get_batch(batch.id)
        assert found is not None
        assert found.id == batch.id

    def test_get_batches_by_app(self, service: BatchService, app_id: int):
        service.create_batch(app_id)
        service.create_batch(app_id)
        batches = service.get_batches_by_app(app_id)
        assert len(batches) == 2

    def test_get_batches_by_state(self, service: BatchService, app_id: int):
        b1 = service.create_batch(app_id)
        service.create_batch(app_id)
        service.transition_state(b1.id, "read")

        created = service.get_batches_by_state("created")
        read = service.get_batches_by_state("read")
        assert len(created) == 1
        assert len(read) == 1

    def test_get_stats(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray], session: Session,
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images)
        pages[0].needs_review = True
        pages[1].is_excluded = True
        session.flush()

        stats = service.get_stats(batch.id)
        assert stats["total_pages"] == 3
        assert stats["needs_review"] == 1
        assert stats["excluded"] == 1

    def test_get_pages_needing_review(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray], session: Session,
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images)
        pages[1].needs_review = True
        session.flush()

        review = service.get_pages_needing_review(batch.id)
        assert len(review) == 1
        assert review[0].id == pages[1].id


# ------------------------------------------------------------------
# Campos y eliminación
# ------------------------------------------------------------------


class TestFieldsAndDeletion:
    def test_get_set_fields(self, service: BatchService, app_id: int):
        batch = service.create_batch(app_id)
        service.set_fields(batch.id, {"ref": "ABC-123"})
        fields = service.get_fields(batch.id)
        assert fields["ref"] == "ABC-123"

    def test_delete_batch(
        self, service: BatchService, app_id: int,
        sample_images: list[np.ndarray],
    ):
        batch = service.create_batch(app_id)
        pages = service.add_pages(batch.id, sample_images[:1])
        image_path = Path(pages[0].image_path)
        batch_dir = image_path.parent

        service.delete_batch(batch.id)
        assert not image_path.exists()
        assert service.get_batch(batch.id) is None
