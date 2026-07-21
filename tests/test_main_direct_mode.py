"""Tests del modo directo de main.py (_run_direct_mode).

Regresión del bug detectado en la auditoría 2026-07-21: main.py importaba
``get_scanner`` (inexistente) en vez de ``create_scanner``, rompiendo todo
el flujo ``--direct-mode``. El ImportError quedaba silenciado por el
try/except de escaneo, por lo que ningún test lo detectaba.
"""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import main as main_mod
from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch
from app.models.barcode import Barcode  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.models.page import Page
from app.models.template import Template  # noqa: F401


@pytest.fixture
def engine():
    """Engine SQLite en memoria con WAL mode."""
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session_factory(engine):
    """Fábrica de sesiones ligada al engine en memoria."""
    return sessionmaker(bind=engine)


@pytest.fixture
def active_app(session_factory) -> str:
    """Inserta una aplicación activa sin transferencia y retorna su nombre."""
    with session_factory() as session:
        app = Application(
            name="DirectApp",
            description="App para modo directo",
            active=True,
            pipeline_json="[]",
            events_json="{}",
            transfer_json="{}",
            auto_transfer=False,
        )
        session.add(app)
        session.commit()
        return app.name


class _FakeScanner:
    """Escáner falso que devuelve una imagen fija."""

    def scan(self) -> list[np.ndarray]:
        return [np.zeros((10, 10, 3), dtype=np.uint8)]


class TestRunDirectMode:
    def test_app_inexistente_devuelve_1(self, session_factory) -> None:
        """Si la aplicación no existe, retorna código de error 1."""
        assert main_mod._run_direct_mode("NoExiste", session_factory) == 1

    def test_flujo_completo_con_scanner_mockeado(
        self, session_factory, active_app, tmp_path, monkeypatch
    ) -> None:
        """El flujo escanear→pipeline→persistir termina con código 0.

        Parchea ``create_scanner`` en su módulo de origen: si el nombre
        dejara de existir (regresión del bug ``get_scanner``), el propio
        monkeypatch.setattr fallaría con AttributeError.
        """
        monkeypatch.setattr(main_mod, "APP_IMAGES_DIR", tmp_path / "images")
        monkeypatch.setattr(
            "app.services.scanner_service.create_scanner",
            lambda backend=None: _FakeScanner(),
        )

        result = main_mod._run_direct_mode(active_app, session_factory)

        assert result == 0
        with session_factory() as session:
            batch = session.query(Batch).one()
            # Sin destino de transferencia, el lote queda listo para exportar
            assert batch.state == "ready_to_export"
            pages = session.query(Page).filter_by(batch_id=batch.id).all()
            assert len(pages) == 1

    def test_error_de_escaneo_devuelve_1(
        self, session_factory, active_app, tmp_path, monkeypatch
    ) -> None:
        """Si el escáner falla, retorna 1 sin crear lote."""
        monkeypatch.setattr(main_mod, "APP_IMAGES_DIR", tmp_path / "images")

        def _boom(backend=None):
            raise RuntimeError("sin escáner")

        monkeypatch.setattr("app.services.scanner_service.create_scanner", _boom)

        assert main_mod._run_direct_mode(active_app, session_factory) == 1
        with session_factory() as session:
            assert session.query(Batch).count() == 0
