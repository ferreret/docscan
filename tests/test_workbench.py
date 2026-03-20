"""Tests del Workbench UI — workers, paneles y ventana de explotación."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.barcode import Barcode  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.workers.recognition_worker import (
    AppContext,
    BatchContext,
    BarcodeResult,
    PageContext,
    PageFlags,
    RecognitionWorker,
)
from app.workers.scan_worker import ScanWorker
from app.workers.transfer_worker import TransferWorker
from app.ui.workbench.page_state import (
    PageState,
    STATE_COLORS,
    determine_page_state,
    ndarray_to_qpixmap,
)
from app.ui.workbench.thumbnail_panel import ThumbnailPanel
from app.ui.workbench.document_viewer import DocumentViewer
from app.ui.workbench.barcode_panel import BarcodePanel
from app.ui.workbench.metadata_panel import MetadataPanel
from app.ui.workbench.workbench_window import WorkbenchWindow


# ==================================================================
# Fixtures comunes
# ==================================================================


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
def session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def sample_app(db_session) -> Application:
    """Crea una aplicación mínima en la BD de prueba."""
    app = Application(
        name="Test App",
        description="App de prueba para workbench",
        pipeline_json="[]",
        events_json="{}",
        transfer_json="{}",
        batch_fields_json='[{"label": "cliente", "type": "texto", "required": false}]',
        index_fields_json='[{"name": "referencia", "type": "Texto", "required": true}]',
        default_tab="lote",
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app


@pytest.fixture
def color_image() -> np.ndarray:
    """Imagen BGR de prueba (100x80, 3 canales)."""
    img = np.zeros((100, 80, 3), dtype=np.uint8)
    img[0:50, :] = [255, 0, 0]   # azul en BGR
    img[50:, :] = [0, 255, 0]    # verde en BGR
    return img


@pytest.fixture
def gray_image() -> np.ndarray:
    """Imagen en escala de grises de prueba (60x40)."""
    return np.full((60, 40), fill_value=128, dtype=np.uint8)


@pytest.fixture
def rgba_image() -> np.ndarray:
    """Imagen BGRA de prueba (50x50, 4 canales)."""
    img = np.zeros((50, 50, 4), dtype=np.uint8)
    img[:, :, 0] = 200  # canal azul
    img[:, :, 3] = 255  # alpha completamente opaco
    return img


# ==================================================================
# ScanWorker
# ==================================================================


class TestScanWorker:
    def test_import_file_emits_pages(self, qtbot, color_image):
        """ScanWorker en modo import_file emite page_acquired por cada imagen."""
        mock_import = MagicMock()
        mock_import.import_file.return_value = [color_image, color_image]

        worker = ScanWorker(
            mode="import_file",
            source="/fake/doc.tiff",
            import_service=mock_import,
        )
        # QThread — no addWidget needed

        acquired = []
        worker.page_acquired.connect(lambda idx, img: acquired.append((idx, img)))

        with qtbot.waitSignal(worker.finished_scanning, timeout=3000) as sig:
            worker.start()

        worker.wait()
        assert sig.args[0] == 2
        assert len(acquired) == 2
        assert acquired[0][0] == 0
        assert acquired[1][0] == 1

    def test_import_folder_delegates_to_service(self, qtbot, color_image):
        """ScanWorker en modo import_folder llama a import_folder del servicio."""
        mock_import = MagicMock()
        mock_import.import_folder.return_value = [color_image]

        worker = ScanWorker(
            mode="import_folder",
            source="/fake/folder",
            import_service=mock_import,
        )
        # QThread — no addWidget needed

        with qtbot.waitSignal(worker.finished_scanning, timeout=3000):
            worker.start()

        worker.wait()
        mock_import.import_folder.assert_called_once_with("/fake/folder", dpi=300)

    def test_import_pdf_delegates_to_service(self, qtbot, color_image):
        """ScanWorker en modo import_pdf llama a import_file del servicio."""
        mock_import = MagicMock()
        mock_import.import_file.return_value = [color_image]

        worker = ScanWorker(
            mode="import_pdf",
            source="/fake/doc.pdf",
            import_service=mock_import,
            dpi=200,
        )
        # QThread — no addWidget needed

        with qtbot.waitSignal(worker.finished_scanning, timeout=3000):
            worker.start()

        worker.wait()
        mock_import.import_file.assert_called_once_with("/fake/doc.pdf", dpi=200)

    def test_scanner_mode_calls_acquire(self, qtbot, color_image):
        """ScanWorker en modo scanner llama a scanner.acquire."""
        mock_scanner = MagicMock()
        mock_scanner.acquire.return_value = [color_image, color_image, color_image]

        worker = ScanWorker(
            mode="scanner",
            source="Escáner HP",
            scanner=mock_scanner,
            scan_config=MagicMock(),
        )
        # QThread — no addWidget needed

        finished_args = []
        worker.finished_scanning.connect(lambda n: finished_args.append(n))

        with qtbot.waitSignal(worker.finished_scanning, timeout=3000):
            worker.start()

        worker.wait()
        assert finished_args[0] == 3
        mock_scanner.acquire.assert_called_once()

    def test_error_emitted_when_no_import_service(self, qtbot):
        """ScanWorker emite error_occurred si import_service es None."""
        worker = ScanWorker(
            mode="import_file",
            source="/fake/doc.tiff",
            import_service=None,
        )
        # QThread — no addWidget needed

        errors = []
        worker.error_occurred.connect(errors.append)

        with qtbot.waitSignal(worker.error_occurred, timeout=3000):
            worker.start()

        worker.wait()
        assert len(errors) == 1
        assert "ImportService" in errors[0]

    def test_error_emitted_when_no_scanner(self, qtbot):
        """ScanWorker emite error_occurred si scanner es None en modo scanner."""
        worker = ScanWorker(
            mode="scanner",
            source="Escáner",
            scanner=None,
        )
        # QThread — no addWidget needed

        errors = []
        worker.error_occurred.connect(errors.append)

        with qtbot.waitSignal(worker.error_occurred, timeout=3000):
            worker.start()

        worker.wait()
        assert "escáner" in errors[0].lower()

    def test_unknown_mode_emits_error(self, qtbot):
        """ScanWorker emite error_occurred con modo desconocido."""
        worker = ScanWorker(
            mode="modo_inexistente",
            source="/fake/path",
        )
        # QThread — no addWidget needed

        errors = []
        worker.error_occurred.connect(errors.append)

        with qtbot.waitSignal(worker.error_occurred, timeout=3000):
            worker.start()

        worker.wait()
        assert len(errors) == 1

    def test_service_exception_emits_error(self, qtbot):
        """ScanWorker captura excepciones del servicio y las emite como error."""
        mock_import = MagicMock()
        mock_import.import_file.side_effect = IOError("Fichero no encontrado")

        worker = ScanWorker(
            mode="import_file",
            source="/nonexistent.tiff",
            import_service=mock_import,
        )
        # QThread — no addWidget needed

        errors = []
        worker.error_occurred.connect(errors.append)

        with qtbot.waitSignal(worker.error_occurred, timeout=3000):
            worker.start()

        worker.wait()
        assert "Fichero no encontrado" in errors[0]


# ==================================================================
# RecognitionWorker — dataclasses
# ==================================================================


class TestPageFlags:
    def test_defaults(self):
        flags = PageFlags()
        assert flags.needs_review is False
        assert flags.review_reason == ""
        assert flags.script_errors == []
        assert flags.processing_errors == []

    def test_mutate_fields(self):
        flags = PageFlags()
        flags.needs_review = True
        flags.review_reason = "Barcode ilegible"
        flags.script_errors.append({"step": "s1", "error": "oops"})
        assert flags.needs_review is True
        assert flags.review_reason == "Barcode ilegible"
        assert len(flags.script_errors) == 1

    def test_script_errors_independent_per_instance(self):
        f1 = PageFlags()
        f2 = PageFlags()
        f1.script_errors.append({"step": "a"})
        assert f2.script_errors == []


class TestBarcodeResult:
    def test_defaults(self):
        bc = BarcodeResult()
        assert bc.value == ""
        assert bc.symbology == ""
        assert bc.engine == ""
        assert bc.step_id == ""
        assert bc.quality == 0.0
        assert bc.pos_x == 0
        assert bc.pos_y == 0
        assert bc.pos_w == 0
        assert bc.pos_h == 0
        assert bc.role == ""

    def test_custom_values(self):
        bc = BarcodeResult(
            value="ABC-123",
            symbology="CODE128",
            engine="pyzbar",
            step_id="step_bc_1",
            quality=0.95,
            pos_x=10,
            pos_y=20,
            pos_w=100,
            pos_h=30,
            role="separator",
        )
        assert bc.value == "ABC-123"
        assert bc.role == "separator"
        assert bc.quality == 0.95


class TestPageContext:
    def test_defaults(self):
        page = PageContext(page_index=0)
        assert page.page_index == 0
        assert page.image is None
        assert page.barcodes == []
        assert page.ocr_text == ""
        assert page.custom_fields == {}
        assert isinstance(page.flags, PageFlags)
        assert page.fields == {}

    def test_with_image(self, color_image):
        page = PageContext(page_index=2, image=color_image)
        assert page.page_index == 2
        assert page.image is color_image

    def test_barcodes_independent_per_instance(self):
        p1 = PageContext(page_index=0)
        p2 = PageContext(page_index=1)
        p1.barcodes.append(BarcodeResult(value="XYZ"))
        assert p2.barcodes == []


class TestBatchContext:
    def test_defaults(self):
        ctx = BatchContext()
        assert ctx.id == 0
        assert ctx.fields == {}
        assert ctx.state == "created"
        assert ctx.page_count == 0
        assert ctx.folder_path == ""
        assert ctx.hostname == ""

    def test_custom(self):
        ctx = BatchContext(id=42, state="read", fields={"ref": "001"})
        assert ctx.id == 42
        assert ctx.state == "read"

    def test_enriched_fields(self):
        ctx = BatchContext(
            id=10, state="read", fields={"ref": "X"},
            page_count=5, folder_path="/tmp/batch", hostname="host1",
        )
        assert ctx.page_count == 5
        assert ctx.folder_path == "/tmp/batch"
        assert ctx.hostname == "host1"


class TestAppContext:
    def test_defaults(self):
        ctx = AppContext()
        assert ctx.id == 0
        assert ctx.name == ""
        assert ctx.description == ""
        assert ctx.config == {}
        assert ctx.batch_fields_def == []
        assert ctx.transfer_config == {}
        assert ctx.auto_transfer is False
        assert ctx.output_format == "tiff"

    def test_custom(self):
        ctx = AppContext(id=7, name="Facturas", description="Procesa facturas")
        assert ctx.id == 7
        assert ctx.name == "Facturas"

    def test_enriched_fields(self):
        ctx = AppContext(
            id=1, name="App",
            batch_fields_def=[{"name": "ref", "type": "text"}],
            transfer_config={"mode": "folder", "destination": "/tmp"},
            auto_transfer=True,
            output_format="png",
        )
        assert len(ctx.batch_fields_def) == 1
        assert ctx.transfer_config["mode"] == "folder"
        assert ctx.auto_transfer is True
        assert ctx.output_format == "png"


# ==================================================================
# RecognitionWorker — QThread
# ==================================================================


class TestRecognitionWorker:
    def _make_executor(self, side_effect=None):
        """Crea un executor mock que simplemente no hace nada (o lanza error)."""
        executor = MagicMock()
        if side_effect:
            executor.execute.side_effect = side_effect
        return executor

    def test_single_page_processed(self, qtbot, color_image):
        """RecognitionWorker procesa una página y emite page_processed."""
        executor = self._make_executor()
        app_ctx = AppContext(id=1, name="Test")
        batch_ctx = BatchContext(id=10)

        worker = RecognitionWorker(
            executor=executor,
            app_context=app_ctx,
            batch_context=batch_ctx,
        )
        # QThread — no addWidget needed

        processed = []
        worker.page_processed.connect(lambda idx, ctx: processed.append((idx, ctx)))

        worker.enqueue_page(0, color_image)
        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=5000):
            worker.start()

        worker.wait()
        assert len(processed) == 1
        assert processed[0][0] == 0
        assert isinstance(processed[0][1], PageContext)
        executor.execute.assert_called_once()

    def test_multiple_pages_processed(self, qtbot, color_image, gray_image):
        """RecognitionWorker procesa múltiples páginas en orden."""
        executor = self._make_executor()
        worker = RecognitionWorker(
            executor=executor,
            app_context=AppContext(id=1),
            batch_context=BatchContext(id=1),
        )
        # QThread — no addWidget needed

        processed_indices = []
        worker.page_processed.connect(lambda idx, ctx: processed_indices.append(idx))

        worker.enqueue_page(0, color_image)
        worker.enqueue_page(1, gray_image)
        worker.enqueue_page(2, color_image)
        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=5000):
            worker.start()

        worker.wait()
        assert sorted(processed_indices) == [0, 1, 2]
        assert executor.execute.call_count == 3

    def test_progress_emitted(self, qtbot, color_image):
        """RecognitionWorker emite progress (completed, total) por cada página."""
        executor = self._make_executor()
        worker = RecognitionWorker(
            executor=executor,
            app_context=AppContext(id=1),
            batch_context=BatchContext(id=1),
        )
        # QThread — no addWidget needed

        progress_events = []
        worker.progress.connect(lambda c, t: progress_events.append((c, t)))

        worker.enqueue_page(0, color_image)
        worker.enqueue_page(1, color_image)
        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=5000):
            worker.start()

        worker.wait()
        assert len(progress_events) == 2
        assert progress_events[-1][0] == 2  # completed == total
        assert progress_events[-1][1] == 2

    def test_page_error_emitted_on_executor_exception(self, qtbot, color_image):
        """RecognitionWorker emite page_error si el executor lanza excepción."""
        executor = self._make_executor(side_effect=RuntimeError("Fallo pipeline"))
        worker = RecognitionWorker(
            executor=executor,
            app_context=AppContext(id=1),
            batch_context=BatchContext(id=1),
        )
        # QThread — no addWidget needed

        errors = []
        worker.page_error.connect(lambda idx, msg: errors.append((idx, msg)))

        worker.enqueue_page(0, color_image)
        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=5000):
            worker.start()

        worker.wait()
        assert len(errors) == 1
        assert errors[0][0] == 0
        assert "Fallo pipeline" in errors[0][1]

    def test_all_processed_emitted_without_pages(self, qtbot):
        """RecognitionWorker emite all_processed aunque la cola esté vacía."""
        executor = self._make_executor()
        worker = RecognitionWorker(
            executor=executor,
            app_context=AppContext(id=1),
            batch_context=BatchContext(id=1),
        )
        # QThread — no addWidget needed

        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=3000):
            worker.start()

        worker.wait()
        executor.execute.assert_not_called()

    def test_executor_receives_correct_contexts(self, qtbot, color_image):
        """El executor recibe page, batch y app context en el orden correcto."""
        executor = self._make_executor()
        app_ctx = AppContext(id=99, name="MiApp")
        batch_ctx = BatchContext(id=55)

        worker = RecognitionWorker(
            executor=executor,
            app_context=app_ctx,
            batch_context=batch_ctx,
        )
        # QThread — no addWidget needed

        worker.enqueue_page(3, color_image)
        worker.signal_no_more_pages()

        with qtbot.waitSignal(worker.all_processed, timeout=5000):
            worker.start()

        worker.wait()
        call_kwargs = executor.execute.call_args
        assert call_kwargs.kwargs["app"] is app_ctx
        assert call_kwargs.kwargs["batch"] is batch_ctx
        assert call_kwargs.kwargs["page"].page_index == 3


# ==================================================================
# TransferWorker
# ==================================================================


class TestTransferWorker:
    def test_transfer_finished_emitted_on_success(self, qtbot):
        """TransferWorker emite transfer_finished con el resultado del servicio."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_transferred = 5
        mock_service.transfer.return_value = mock_result

        worker = TransferWorker(
            transfer_service=mock_service,
            config=MagicMock(),
            pages=[{"image_path": "/img/p1.tiff"}],
            batch_fields={"cliente": "ACME"},
            batch_id=7,
        )
        # QThread — no addWidget needed

        results = []
        worker.transfer_finished.connect(results.append)

        with qtbot.waitSignal(worker.transfer_finished, timeout=3000):
            worker.start()

        worker.wait()
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].files_transferred == 5

    def test_transfer_error_emitted_on_exception(self, qtbot):
        """TransferWorker emite transfer_error si el servicio lanza excepción."""
        mock_service = MagicMock()
        mock_service.transfer.side_effect = ConnectionError("Sin conexión")

        worker = TransferWorker(
            transfer_service=mock_service,
            config=MagicMock(),
            pages=[],
            batch_fields={},
            batch_id=1,
        )
        # QThread — no addWidget needed

        errors = []
        worker.transfer_error.connect(errors.append)

        with qtbot.waitSignal(worker.transfer_error, timeout=3000):
            worker.start()

        worker.wait()
        assert len(errors) == 1
        assert "Sin conexión" in errors[0]

    def test_service_called_with_correct_args(self, qtbot):
        """TransferWorker pasa correctamente todos los argumentos al servicio."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_service.transfer.return_value = mock_result

        config = MagicMock()
        config.standard_enabled = True
        pages = [{"image_path": "/img/p1.tiff", "page_index": 0}]
        batch_fields = {"ref": "REF-001"}

        worker = TransferWorker(
            transfer_service=mock_service,
            config=config,
            pages=pages,
            batch_fields=batch_fields,
            batch_id=42,
        )
        # QThread — no addWidget needed

        with qtbot.waitSignal(worker.transfer_finished, timeout=3000):
            worker.start()

        worker.wait()
        call_kwargs = mock_service.transfer.call_args
        assert call_kwargs.kwargs["pages"] == pages
        assert call_kwargs.kwargs["config"] is config
        assert call_kwargs.kwargs["batch_fields"] == batch_fields
        assert call_kwargs.kwargs["batch_id"] == 42


# ==================================================================
# page_state: determine_page_state
# ==================================================================


class TestDeterminePageState:
    def test_needs_review_has_highest_priority(self):
        """needs_review tiene prioridad sobre separadores y campos IA."""
        bc = BarcodeResult(role="separator")
        state = determine_page_state(
            needs_review=True,
            barcodes=[bc],
            custom_fields_json='{"campo": "valor"}',
        )
        assert state is PageState.NEEDS_REVIEW

    def test_separator_barcode_priority_over_ai(self):
        """Separador tiene prioridad sobre campos IA."""
        bc = BarcodeResult(role="separator")
        state = determine_page_state(
            needs_review=False,
            barcodes=[bc],
            custom_fields_json='{"campo": "valor"}',
        )
        assert state is PageState.SEPARATOR_BARCODE

    def test_custom_fields_priority_over_barcode_no_role(self):
        """Campos IA tienen prioridad sobre barcodes sin rol."""
        bc = BarcodeResult(role="")
        state = determine_page_state(
            needs_review=False,
            barcodes=[bc],
            custom_fields_json='{"nombre": "Juan"}',
        )
        assert state is PageState.CUSTOM_FIELDS

    def test_barcode_no_role(self):
        """Barcode sin rol devuelve BARCODE_NO_ROLE."""
        bc = BarcodeResult(role="")
        state = determine_page_state(
            needs_review=False,
            barcodes=[bc],
            custom_fields_json="{}",
        )
        assert state is PageState.BARCODE_NO_ROLE

    def test_no_recognition(self):
        """Sin barcodes ni campos IA, el estado es NO_RECOGNITION."""
        state = determine_page_state(
            needs_review=False,
            barcodes=[],
            custom_fields_json="{}",
        )
        assert state is PageState.NO_RECOGNITION

    def test_no_recognition_empty_defaults(self):
        """Valores por defecto producen NO_RECOGNITION."""
        state = determine_page_state()
        assert state is PageState.NO_RECOGNITION

    def test_none_barcodes_treated_as_empty(self):
        """barcodes=None se trata como lista vacía."""
        state = determine_page_state(needs_review=False, barcodes=None)
        assert state is PageState.NO_RECOGNITION

    def test_custom_fields_json_null_is_no_recognition(self):
        """custom_fields_json 'null' se trata como vacío."""
        state = determine_page_state(
            needs_review=False,
            barcodes=[],
            custom_fields_json="null",
        )
        assert state is PageState.NO_RECOGNITION

    def test_custom_fields_json_empty_string(self):
        """custom_fields_json '' se trata como vacío."""
        state = determine_page_state(
            needs_review=False,
            barcodes=[],
            custom_fields_json="",
        )
        assert state is PageState.NO_RECOGNITION

    def test_custom_fields_non_empty(self):
        """JSON no vacío activa el estado CUSTOM_FIELDS."""
        state = determine_page_state(
            needs_review=False,
            barcodes=[],
            custom_fields_json='{"key": "val"}',
        )
        assert state is PageState.CUSTOM_FIELDS

    def test_multiple_barcodes_one_separator(self):
        """Uno de varios barcodes con rol separator activa SEPARATOR_BARCODE."""
        bcs = [
            BarcodeResult(role=""),
            BarcodeResult(role="separator"),
            BarcodeResult(role=""),
        ]
        state = determine_page_state(needs_review=False, barcodes=bcs)
        assert state is PageState.SEPARATOR_BARCODE

    def test_all_states_have_colors(self):
        """Todos los estados tienen un color definido en STATE_COLORS."""
        for state in PageState:
            assert state in STATE_COLORS
            assert STATE_COLORS[state].startswith("#")


# ==================================================================
# page_state: ndarray_to_qpixmap
# ==================================================================


class TestNdarrayToQpixmap:
    def test_color_image_returns_qpixmap(self, qtbot, color_image):
        """Imagen BGR produce un QPixmap no nulo."""
        pixmap = ndarray_to_qpixmap(color_image)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() == color_image.shape[1]
        assert pixmap.height() == color_image.shape[0]

    def test_grayscale_image_returns_qpixmap(self, qtbot, gray_image):
        """Imagen en escala de grises produce un QPixmap no nulo."""
        pixmap = ndarray_to_qpixmap(gray_image)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() == gray_image.shape[1]
        assert pixmap.height() == gray_image.shape[0]

    def test_rgba_image_returns_qpixmap(self, qtbot, rgba_image):
        """Imagen BGRA (4 canales) produce un QPixmap no nulo."""
        pixmap = ndarray_to_qpixmap(rgba_image)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() == rgba_image.shape[1]
        assert pixmap.height() == rgba_image.shape[0]

    def test_none_returns_empty_qpixmap(self, qtbot):
        """None devuelve un QPixmap vacío."""
        pixmap = ndarray_to_qpixmap(None)
        assert isinstance(pixmap, QPixmap)
        assert pixmap.isNull()

    def test_single_pixel_image(self, qtbot):
        """Imagen de 1x1 no produce error."""
        img = np.array([[[100, 150, 200]]], dtype=np.uint8)
        pixmap = ndarray_to_qpixmap(img)
        assert not pixmap.isNull()
        assert pixmap.width() == 1
        assert pixmap.height() == 1

    def test_large_image(self, qtbot):
        """Imagen grande (3000x2000) se convierte correctamente."""
        img = np.zeros((2000, 3000, 3), dtype=np.uint8)
        pixmap = ndarray_to_qpixmap(img)
        assert not pixmap.isNull()
        assert pixmap.width() == 3000
        assert pixmap.height() == 2000


# ==================================================================
# ThumbnailPanel
# ==================================================================


class TestThumbnailPanel:
    def test_empty_on_creation(self, qtbot):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)
        assert panel.count == 0

    def test_add_thumbnail_increases_count(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        assert panel.count == 1

    def test_add_multiple_thumbnails(self, qtbot, color_image, gray_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.add_thumbnail(1, gray_image)
        panel.add_thumbnail(2, color_image)
        assert panel.count == 3

    def test_add_thumbnail_with_explicit_state(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image, state=PageState.NEEDS_REVIEW)
        assert panel._states[0] is PageState.NEEDS_REVIEW

    def test_add_thumbnail_default_state(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        assert panel._states[0] is PageState.NO_RECOGNITION

    def test_set_current_selects_thumbnail(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.add_thumbnail(1, color_image)
        panel.set_current(1)

        assert panel._current_index == 1

    def test_set_current_deselects_previous(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.add_thumbnail(1, color_image)
        panel.set_current(0)
        panel.set_current(1)

        # El anterior debe quedar desmarcado
        assert panel._thumbnails[0]._selected is False
        assert panel._thumbnails[1]._selected is True

    def test_set_current_nonexistent_index(self, qtbot, color_image):
        """set_current con índice no existente no lanza excepción."""
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.set_current(99)  # no debe lanzar
        assert panel._current_index == 99

    def test_update_thumbnail_state(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image, state=PageState.NO_RECOGNITION)
        panel.update_thumbnail_state(0, PageState.NEEDS_REVIEW)

        assert panel._states[0] is PageState.NEEDS_REVIEW

    def test_update_thumbnail_state_nonexistent(self, qtbot):
        """update_thumbnail_state con índice no existente no lanza excepción."""
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.update_thumbnail_state(99, PageState.NEEDS_REVIEW)  # no debe lanzar

    def test_clear_removes_all(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.add_thumbnail(1, color_image)
        panel.clear()

        assert panel.count == 0
        assert panel._current_index == -1
        assert panel._states == {}

    def test_page_selected_signal(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)

        with qtbot.waitSignal(panel.page_selected, timeout=1000) as sig:
            panel._on_item_clicked(0)

        assert sig.args[0] == 0

    def test_page_selected_updates_current(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.add_thumbnail(1, color_image)
        panel._on_item_clicked(1)

        assert panel._current_index == 1

    def test_clear_resets_current_index(self, qtbot, color_image):
        panel = ThumbnailPanel()
        qtbot.addWidget(panel)

        panel.add_thumbnail(0, color_image)
        panel.set_current(0)
        panel.clear()

        assert panel._current_index == -1


# ==================================================================
# DocumentViewer
# ==================================================================


class TestDocumentViewer:
    def test_creates_without_error(self, qtbot):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        assert viewer is not None

    def test_set_image_displays_pixmap(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        assert viewer._pixmap_item is not None
        assert not viewer._pixmap_item.pixmap().isNull()

    def test_set_image_grayscale(self, qtbot, gray_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(gray_image, PageState.NO_RECOGNITION)
        assert viewer._pixmap_item is not None

    def test_set_image_updates_border(self, qtbot, color_image):
        """set_image establece el color del borde según el estado."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NEEDS_REVIEW)
        style = viewer.styleSheet()
        assert "#e53935" in style  # rojo para NEEDS_REVIEW

    def test_set_state_changes_border_color(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        viewer.set_state(PageState.CUSTOM_FIELDS)
        style = viewer.styleSheet()
        assert "#1e88e5" in style  # azul para CUSTOM_FIELDS

    def test_clear_removes_pixmap(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        viewer.clear()

        assert viewer._pixmap_item is None

    def test_clear_overlays(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        bc = BarcodeResult(pos_x=10, pos_y=10, pos_w=50, pos_h=20)
        viewer.set_overlays(barcodes=[bc])
        assert len(viewer._overlay_items) == 1

        viewer.clear_overlays()
        assert len(viewer._overlay_items) == 0

    def test_set_overlays_with_barcodes(self, qtbot, color_image):
        """set_overlays añade items de overlay para cada barcode con dimensiones."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        barcodes = [
            BarcodeResult(pos_x=0, pos_y=0, pos_w=40, pos_h=20),
            BarcodeResult(pos_x=50, pos_y=50, pos_w=30, pos_h=15),
        ]
        viewer.set_overlays(barcodes=barcodes)
        assert len(viewer._overlay_items) == 2

    def test_set_overlays_skips_zero_dimension_barcodes(self, qtbot, color_image):
        """Barcodes con dimensión 0 no generan overlay."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        barcodes = [
            BarcodeResult(pos_x=0, pos_y=0, pos_w=0, pos_h=0),  # sin dimensiones
            BarcodeResult(pos_x=10, pos_y=10, pos_w=40, pos_h=20),  # válido
        ]
        viewer.set_overlays(barcodes=barcodes)
        assert len(viewer._overlay_items) == 1

    def test_set_overlays_separator_different_color(self, qtbot, color_image):
        """Barcodes con role=separator generan overlays de color diferente."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        barcodes = [
            BarcodeResult(role="separator", pos_x=0, pos_y=0, pos_w=50, pos_h=25),
        ]
        viewer.set_overlays(barcodes=barcodes)
        assert len(viewer._overlay_items) == 1

    def test_set_overlays_clears_previous(self, qtbot, color_image):
        """set_overlays borra los overlays anteriores antes de dibujar los nuevos."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        viewer.set_overlays(barcodes=[BarcodeResult(pos_x=0, pos_y=0, pos_w=20, pos_h=10)])
        viewer.set_overlays(barcodes=[
            BarcodeResult(pos_x=0, pos_y=0, pos_w=20, pos_h=10),
            BarcodeResult(pos_x=30, pos_y=30, pos_w=20, pos_h=10),
        ])
        assert len(viewer._overlay_items) == 2

    def test_zoom_in_increases_zoom(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        initial_zoom = viewer._current_zoom
        viewer.zoom_in()
        assert viewer._current_zoom > initial_zoom

    def test_zoom_out_decreases_zoom(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        initial_zoom = viewer._current_zoom
        viewer.zoom_out()
        assert viewer._current_zoom < initial_zoom

    def test_zoom_in_respects_max_limit(self, qtbot, color_image):
        """zoom_in no supera MAX_ZOOM."""
        from app.ui.workbench.document_viewer import MAX_ZOOM

        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        # Zoom extremo
        viewer._current_zoom = MAX_ZOOM
        viewer.zoom_in()
        assert viewer._current_zoom == MAX_ZOOM  # no debe cambiar

    def test_zoom_out_respects_min_limit(self, qtbot, color_image):
        """zoom_out no baja de MIN_ZOOM."""
        from app.ui.workbench.document_viewer import MIN_ZOOM

        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        viewer._current_zoom = MIN_ZOOM
        viewer.zoom_out()
        assert viewer._current_zoom == MIN_ZOOM  # no debe cambiar

    def test_fit_to_page_resets_zoom(self, qtbot, color_image):
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.resize(600, 800)

        viewer.set_image(color_image, PageState.NO_RECOGNITION)
        viewer.zoom_in()
        viewer.zoom_in()
        viewer.fit_to_page()
        assert viewer._current_zoom == 1.0

    def test_fit_to_page_no_pixmap(self, qtbot):
        """fit_to_page no lanza si no hay imagen."""
        viewer = DocumentViewer()
        qtbot.addWidget(viewer)
        viewer.fit_to_page()  # no debe lanzar


# ==================================================================
# BarcodePanel
# ==================================================================


class TestBarcodePanel:
    def test_creates_without_error(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)
        assert panel is not None

    def test_empty_on_creation(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)
        assert panel._table.rowCount() == 0

    def test_set_page_barcodes_populates_table(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        barcodes = [
            BarcodeResult(value="ABC-123", symbology="CODE128", engine="pyzbar", role=""),
            BarcodeResult(value="SEP-001", symbology="QR", engine="zxing", role="separator"),
        ]
        panel.set_page_barcodes(barcodes)

        assert panel._table.rowCount() == 2
        # Columna 0 es indicador de color, datos empiezan en columna 1
        assert panel._table.item(0, 1).text() == "ABC-123"
        assert panel._table.item(0, 2).text() == "CODE128"
        assert panel._table.item(0, 3).text() == "pyzbar"
        assert panel._table.item(0, 4).text() == ""
        assert panel._table.item(1, 4).text() == "separator"

    def test_set_page_barcodes_replaces_previous(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        panel.set_page_barcodes([BarcodeResult(value="OLD")])
        panel.set_page_barcodes([
            BarcodeResult(value="NEW-1"),
            BarcodeResult(value="NEW-2"),
            BarcodeResult(value="NEW-3"),
        ])

        assert panel._table.rowCount() == 3
        assert panel._table.item(0, 1).text() == "NEW-1"

    def test_set_page_barcodes_empty_clears_table(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        panel.set_page_barcodes([BarcodeResult(value="X")])
        panel.set_page_barcodes([])

        assert panel._table.rowCount() == 0

    def test_set_lot_counters(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        panel.set_lot_counters({
            "total_pages": 42,
            "with_barcode": 15,
            "separators": 3,
            "needs_review": 7,
        })

        assert "42" in panel._lbl_total.text()
        assert "15" in panel._lbl_with_barcode.text()
        assert "3" in panel._lbl_separators.text()
        assert "7" in panel._lbl_review.text()

    def test_set_lot_counters_missing_keys(self, qtbot):
        """set_lot_counters con dict vacío usa 0 por defecto."""
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        panel.set_lot_counters({})

        assert "0" in panel._lbl_total.text()
        assert "0" in panel._lbl_with_barcode.text()

    def test_clear_empties_table_and_counters(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)

        panel.set_page_barcodes([BarcodeResult(value="X"), BarcodeResult(value="Y")])
        panel.set_lot_counters({
            "total_pages": 10,
            "with_barcode": 5,
            "separators": 1,
            "needs_review": 2,
        })
        panel.clear()

        assert panel._table.rowCount() == 0
        assert "0" in panel._lbl_total.text()
        assert "0" in panel._lbl_with_barcode.text()
        assert "0" in panel._lbl_separators.text()
        assert "0" in panel._lbl_review.text()

    def test_table_has_five_columns(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)
        assert panel._table.columnCount() == 5

    def test_table_headers(self, qtbot):
        panel = BarcodePanel()
        qtbot.addWidget(panel)
        headers = [panel._table.horizontalHeaderItem(i).text() for i in range(5)]
        assert headers == ["", "Valor", "Simbología", "Motor", "Rol"]


# ==================================================================
# MetadataPanel
# ==================================================================


class TestMetadataPanel:
    @pytest.fixture
    def panel(self, qtbot):
        p = MetadataPanel()
        qtbot.addWidget(p)
        return p

    @pytest.fixture
    def batch_fields_def(self):
        return [
            {"name": "cliente", "type": "Texto", "required": True},
            {"name": "tipo", "type": "Lista", "required": False, "choices": ["A", "B", "C"]},
            {"name": "activo", "type": "Booleano", "required": False},
            {"name": "cantidad", "type": "Número", "required": False},
        ]

    @pytest.fixture
    def index_fields_def(self):
        return [
            {"name": "referencia", "type": "Texto", "required": True},
            {"name": "fecha", "type": "Fecha", "required": False},
        ]

    def test_creates_without_error(self, panel):
        assert panel is not None

    def test_tabs_lote_and_log(self, panel):
        assert panel._tabs.count() == 2
        assert panel._tabs.tabText(0) == "Lote"
        assert panel._tabs.tabText(1) == "Log"

    def test_configure_creates_batch_widgets(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        assert "cliente" in panel._batch_widgets
        assert "tipo" in panel._batch_widgets
        assert "activo" in panel._batch_widgets
        assert "cantidad" in panel._batch_widgets

    def test_configure_creates_correct_widget_types(self, panel, batch_fields_def, index_fields_def):
        from PySide6.QtWidgets import QLineEdit, QComboBox, QCheckBox, QSpinBox

        panel.configure(batch_fields_def, index_fields_def)
        assert isinstance(panel._batch_widgets["cliente"], QLineEdit)
        assert isinstance(panel._batch_widgets["tipo"], QComboBox)
        assert isinstance(panel._batch_widgets["activo"], QCheckBox)
        assert isinstance(panel._batch_widgets["cantidad"], QSpinBox)

    def test_configure_combo_has_choices(self, panel, batch_fields_def, index_fields_def):
        from PySide6.QtWidgets import QComboBox

        panel.configure(batch_fields_def, index_fields_def)
        combo = panel._batch_widgets["tipo"]
        assert isinstance(combo, QComboBox)
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items == ["A", "B", "C"]

    def test_set_batch_fields(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cliente": "ACME Corp", "tipo": "B"})

        from PySide6.QtWidgets import QLineEdit, QComboBox

        assert isinstance(panel._batch_widgets["cliente"], QLineEdit)
        assert panel._batch_widgets["cliente"].text() == "ACME Corp"
        assert isinstance(panel._batch_widgets["tipo"], QComboBox)
        assert panel._batch_widgets["tipo"].currentText() == "B"

    def test_get_batch_fields(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cliente": "TestCliente"})

        values = panel.get_batch_fields()
        assert values["cliente"] == "TestCliente"

    def test_set_index_fields_stub(self, panel):
        """set_index_fields es un stub que no hace nada (pestaña desactivada)."""
        panel.set_index_fields({"referencia": "REF-001"})  # No debe crashear

    def test_get_index_fields_returns_empty(self, panel):
        """get_index_fields retorna dict vacío (pestaña desactivada)."""
        assert panel.get_index_fields() == {}

    def test_set_batch_fields_missing_key_uses_empty(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({})  # ningún campo especificado

        from PySide6.QtWidgets import QLineEdit

        assert panel._batch_widgets["cliente"].text() == ""

    def test_set_verification_data_stub(self, panel):
        """set_verification_data es un stub que no crashea."""
        panel.set_verification_data(ocr_text="Texto OCR de prueba")

    def test_set_default_tab_lote(self, panel):
        panel.set_default_tab("lote")
        assert panel._tabs.currentIndex() == 0

    def test_set_default_tab_unknown_defaults_to_lote(self, panel):
        panel.set_default_tab("desconocido")
        assert panel._tabs.currentIndex() == 0

    def test_clear_resets_batch_fields(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cliente": "ACME"})
        panel.clear()

        from PySide6.QtWidgets import QLineEdit

        assert panel._batch_widgets["cliente"].text() == ""

    def test_clear_no_crash(self, panel, batch_fields_def, index_fields_def):
        """clear() no crashea incluso sin widgets configurados."""
        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cliente": "Test"})
        panel.clear()
        assert panel._batch_widgets["cliente"].text() == ""

    def test_batch_field_changed_signal(self, panel, batch_fields_def, index_fields_def, qtbot):
        panel.configure(batch_fields_def, index_fields_def)

        from PySide6.QtWidgets import QLineEdit

        widget = panel._batch_widgets["cliente"]
        assert isinstance(widget, QLineEdit)

        with qtbot.waitSignal(panel.batch_field_changed, timeout=1000) as sig:
            widget.setText("NuevoValor")
            widget.editingFinished.emit()

        assert sig.args[0] == "cliente"
        assert sig.args[1] == "NuevoValor"

    def test_configure_clears_previous_widgets(self, panel, batch_fields_def, index_fields_def):
        panel.configure(batch_fields_def, index_fields_def)
        assert len(panel._batch_widgets) == 4

        # Reconfigurar con menos campos
        panel.configure(
            [{"name": "solo_uno", "type": "Texto", "required": False}],
            [],
        )
        assert len(panel._batch_widgets) == 1
        assert "solo_uno" in panel._batch_widgets
        assert "cliente" not in panel._batch_widgets

    def test_spinbox_set_value(self, panel, batch_fields_def, index_fields_def):
        """set_batch_fields convierte correctamente valores numéricos para QSpinBox."""
        from PySide6.QtWidgets import QSpinBox

        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cantidad": "42"})

        widget = panel._batch_widgets["cantidad"]
        assert isinstance(widget, QSpinBox)
        assert widget.value() == 42

    def test_spinbox_invalid_value_defaults_to_zero(self, panel, batch_fields_def, index_fields_def):
        from PySide6.QtWidgets import QSpinBox

        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"cantidad": "no_es_numero"})

        widget = panel._batch_widgets["cantidad"]
        assert isinstance(widget, QSpinBox)
        assert widget.value() == 0

    def test_checkbox_set_true(self, panel, batch_fields_def, index_fields_def):
        from PySide6.QtWidgets import QCheckBox

        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"activo": "true"})

        widget = panel._batch_widgets["activo"]
        assert isinstance(widget, QCheckBox)
        assert widget.isChecked() is True

    def test_checkbox_set_false(self, panel, batch_fields_def, index_fields_def):
        from PySide6.QtWidgets import QCheckBox

        panel.configure(batch_fields_def, index_fields_def)
        panel.set_batch_fields({"activo": "false"})

        widget = panel._batch_widgets["activo"]
        assert isinstance(widget, QCheckBox)
        assert widget.isChecked() is False


# ==================================================================
# WorkbenchWindow — integración
# ==================================================================


class TestWorkbenchWindow:
    """Tests de integración de WorkbenchWindow con BD en memoria."""

    @pytest.fixture
    def workbench(self, qtbot, session_factory, sample_app, tmp_path):
        """Crea un WorkbenchWindow con una aplicación mínima."""
        with patch("app.ui.workbench.workbench_window.APP_DATA_DIR", tmp_path):
            window = WorkbenchWindow(
                app_id=sample_app.id,
                session_factory=session_factory,
            )
        qtbot.addWidget(window)
        return window

    def test_window_title_contains_app_name(self, workbench, sample_app):
        assert sample_app.name in workbench.windowTitle()
        assert "DocScan Studio" in workbench.windowTitle()

    def test_window_minimum_size(self, workbench):
        size = workbench.minimumSize()
        assert size.width() >= 1024
        assert size.height() >= 700

    def test_panels_exist(self, workbench):
        """Los paneles principales existen y son del tipo correcto."""
        assert isinstance(workbench._thumbnail_panel, ThumbnailPanel)
        assert isinstance(workbench._viewer, DocumentViewer)
        assert isinstance(workbench._barcode_panel, BarcodePanel)
        assert isinstance(workbench._metadata_panel, MetadataPanel)

    def test_batch_created_on_init(self, workbench):
        """Al crear el workbench se crea automáticamente un lote."""
        assert workbench._batch_id is not None
        assert workbench._batch_id > 0

    def test_application_loaded(self, workbench, sample_app):
        """La aplicación se carga correctamente desde BD."""
        assert workbench._application is not None
        assert workbench._application.id == sample_app.id
        assert workbench._application.name == sample_app.name

    def test_executor_created(self, workbench):
        """PipelineExecutor se crea durante la inicialización."""
        assert workbench._executor is not None

    def test_page_info_starts_at_zero(self, workbench):
        """El indicador de páginas comienza en 0/0."""
        assert "0" in workbench._viewer_overlay._lbl_page_info.text()

    def test_process_button_exists(self, workbench):
        assert workbench._btn_process is not None
        assert workbench._btn_process.isEnabled()

    def test_transfer_button_exists(self, workbench):
        assert workbench._btn_transfer is not None
        assert workbench._btn_transfer.isEnabled()

    def test_navigation_buttons_exist(self, workbench):
        overlay = workbench._viewer_overlay
        assert overlay._btn_first is not None
        assert overlay._btn_prev is not None
        assert overlay._btn_next is not None
        assert overlay._btn_last is not None

    def test_navigate_to_empty_does_nothing(self, workbench):
        """_navigate_to cuando no hay páginas no lanza excepción."""
        workbench._navigate_to(0)  # no debe lanzar
        assert workbench._current_page_index == -1

    def test_navigate_to_negative_index_ignored(self, workbench):
        """_navigate_to con índice negativo no lanza excepción."""
        workbench._navigate_to(-1)  # no debe lanzar

    def test_on_first_empty_batch(self, workbench):
        workbench._on_first()  # no debe lanzar
        assert workbench._current_page_index == -1

    def test_on_prev_empty_batch(self, workbench):
        workbench._on_prev()  # no debe lanzar

    def test_on_next_empty_batch(self, workbench):
        workbench._on_next()  # no debe lanzar

    def test_on_last_empty_batch(self, workbench):
        workbench._on_last()  # no debe lanzar

    def test_on_next_barcode_empty_batch(self, workbench):
        workbench._on_next_barcode()  # no debe lanzar

    def test_on_next_review_empty_batch(self, workbench):
        workbench._on_next_review()  # no debe lanzar

    def test_on_mark_page_without_selection(self, workbench):
        """_on_mark_page sin página seleccionada no lanza excepción."""
        workbench._on_mark_page()  # no debe lanzar

    def test_invalid_app_id_raises_value_error(self, qtbot, session_factory, tmp_path):
        """WorkbenchWindow con app_id inexistente lanza ValueError."""
        with patch("app.ui.workbench.workbench_window.APP_DATA_DIR", tmp_path):
            with pytest.raises(ValueError, match="no encontrada"):
                window = WorkbenchWindow(
                    app_id=99999,
                    session_factory=session_factory,
                )
                qtbot.addWidget(window)

    def test_closed_signal_on_close(self, qtbot, session_factory, sample_app, tmp_path):
        """Al cerrar la ventana se emite la señal closed."""
        with patch("app.ui.workbench.workbench_window.APP_DATA_DIR", tmp_path):
            window = WorkbenchWindow(
                app_id=sample_app.id,
                session_factory=session_factory,
            )
        qtbot.addWidget(window)

        with qtbot.waitSignal(window.closed, timeout=3000):
            window.close()

    def test_page_info_label_updates_when_pages_added(
        self, qtbot, workbench, session_factory, tmp_path, color_image,
    ):
        """El indicador de página se actualiza al añadir páginas manualmente."""
        from app.services.batch_service import BatchService

        with session_factory() as session:
            svc = BatchService(session, tmp_path / "images")
            pages = svc.add_pages(workbench._batch_id, [color_image, color_image])
            session.commit()
            for p in pages:
                session.expunge(p)
                workbench._pages.append(p)

        workbench._update_page_info()
        assert "2" in workbench._viewer_overlay._lbl_page_info.text()

    def test_update_lot_counters_no_error(self, workbench):
        """_update_lot_counters no lanza con lote vacío."""
        workbench._update_lot_counters()  # no debe lanzar

    def test_metadata_panel_configured(self, workbench):
        """Los campos de lote se configuran desde la app."""
        assert "cliente" in workbench._metadata_panel._batch_widgets

    def test_default_tab_set_from_app(self, workbench):
        """La pestaña por defecto del panel de metadatos se configura desde la app."""
        # sample_app tiene default_tab = "lote"
        assert workbench._metadata_panel._tabs.currentIndex() == 0

    def test_background_color_applied(self, qtbot, session_factory, tmp_path):
        """Si la app tiene background_color, se aplica el estilo."""
        with session_factory() as session:
            app = Application(
                name="ColorApp",
                background_color="#ff0000",
            )
            session.add(app)
            session.commit()
            app_id = app.id

        with patch("app.ui.workbench.workbench_window.APP_DATA_DIR", tmp_path):
            window = WorkbenchWindow(
                app_id=app_id,
                session_factory=session_factory,
            )
        qtbot.addWidget(window)

        assert "#ff0000" in window.styleSheet()

    def test_fire_event_no_script_does_not_crash(self, workbench):
        """_fire_event con un evento sin script no lanza excepción."""
        result = workbench._fire_event("on_app_start")
        # No hay script configurado, debe devolver None silenciosamente
        assert result is None

    def test_workers_initially_none(self, workbench):
        assert workbench._scan_worker is None
        assert workbench._recognition_worker is None
        assert workbench._transfer_worker is None

    def test_scan_source_radio_defaults_to_import(self, workbench):
        """El radio button de importar está seleccionado por defecto."""
        assert workbench._radio_import.isChecked()
        assert not workbench._radio_scanner.isChecked()

    def test_build_app_context_enriched(self, workbench):
        """_build_app_context devuelve campos enriquecidos."""
        ctx = workbench._build_app_context()
        assert ctx.id == workbench._app_id
        assert ctx.name == workbench._application.name
        assert isinstance(ctx.config, dict)
        assert isinstance(ctx.batch_fields_def, list)
        assert isinstance(ctx.transfer_config, dict)
        assert ctx.output_format == (workbench._application.output_format or "tiff")

    def test_build_batch_context_enriched(self, workbench):
        """_build_batch_context devuelve campos enriquecidos."""
        ctx = workbench._build_batch_context()
        assert ctx.id == workbench._batch_id
        assert isinstance(ctx.fields, dict)
        assert isinstance(ctx.state, str)

    def test_fire_event_with_extra_kwargs(self, workbench):
        """_fire_event pasa extra_ctx correctamente."""
        result = workbench._fire_event("on_key_event", key="A")
        assert result is None  # No hay script, pero no debe crashear

    def test_source_type_combo_exists(self, workbench):
        """El combo de source_type (ADF/Flatbed) existe en la toolbar."""
        assert hasattr(workbench, "_combo_source_type")
        assert workbench._combo_source_type.count() == 2
        assert workbench._combo_source_type.itemData(0) == "flatbed"
        assert workbench._combo_source_type.itemData(1) == "adf"
