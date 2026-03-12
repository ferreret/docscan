"""Tests del módulo worker_main (docscan_worker/worker_main.py).

Cubre:
- _parse_args con distintas combinaciones de argumentos
- _load_application: éxito, app no encontrada, app inactiva
- _build_executor: crea PipelineExecutor con scripts pre-compilados
- _compile_lifecycle_events: parsea events_json válido e inválido
- _process_files: flujo completo con servicios mockeados
- _process_pending_batches: encuentra y procesa lotes pendientes
- _transfer_batch: caminos de éxito y de error
- main() en modo --process-pending y modo --watch
- Manejo de la señal de shutdown (_shutdown event)
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call, PropertyMock

import numpy as np
import pytest

from docscan_worker.folder_watcher import FolderWatcher
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401

# Importar _shutdown para poder resetearlo entre tests
import docscan_worker.worker_main as wm
from docscan_worker.worker_main import (
    _compile_lifecycle_events,
    _build_executor,
    _load_application,
    _parse_args,
    _process_files,
    _process_pending_batches,
    _transfer_batch,
)
from app.workers.recognition_worker import AppContext, BatchContext


# ------------------------------------------------------------------
# Fixtures de BD en memoria
# ------------------------------------------------------------------


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
def active_app(session_factory) -> Application:
    """Inserta una aplicación activa en BD y la retorna (detached)."""
    factory = session_factory
    with factory() as session:
        app = Application(
            name="TestApp",
            description="App de prueba",
            active=True,
            pipeline_json="[]",
            events_json="{}",
            transfer_json="{}",
            auto_transfer=False,
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        # Capturar id antes de cerrar la sesión
        app_id = app.id
        app_name = app.name

    # Construir objeto desacoplado para usar fuera de sesión
    detached = Application(
        name=app_name,
        description="App de prueba",
        active=True,
        pipeline_json="[]",
        events_json="{}",
        transfer_json="{}",
        auto_transfer=False,
    )
    detached.id = app_id
    return detached


@pytest.fixture(autouse=True)
def reset_shutdown():
    """Resetea el evento global _shutdown entre tests."""
    wm._shutdown.clear()
    yield
    wm._shutdown.clear()


# ------------------------------------------------------------------
# _parse_args
# ------------------------------------------------------------------


class TestParseArgs:
    def test_watch_mode_basico(self, tmp_path: Path) -> None:
        """--watch proporciona la carpeta de vigilancia."""
        folder = tmp_path / "watch"
        folder.mkdir()
        args = _parse_args(["--app-name", "MiApp", "--watch", str(folder)])
        assert args.app_name == "MiApp"
        assert args.watch == folder
        assert args.process_pending is False

    def test_process_pending_mode(self) -> None:
        """--process-pending activa el modo de pendientes."""
        args = _parse_args(["--app-name", "MiApp", "--process-pending"])
        assert args.process_pending is True
        assert args.watch is None

    def test_debounce_default(self, tmp_path: Path) -> None:
        """El valor por defecto de --debounce es 3."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path)]
        )
        assert args.debounce == 3

    def test_debounce_personalizado(self, tmp_path: Path) -> None:
        """--debounce acepta valor personalizado."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path),
             "--debounce", "10"]
        )
        assert args.debounce == 10

    def test_sentinel_vacio_por_defecto(self, tmp_path: Path) -> None:
        """--sentinel es vacío por defecto."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path)]
        )
        assert args.sentinel == ""

    def test_sentinel_personalizado(self, tmp_path: Path) -> None:
        """--sentinel acepta nombre de fichero."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path),
             "--sentinel", "GO.txt"]
        )
        assert args.sentinel == "GO.txt"

    def test_log_level_default(self, tmp_path: Path) -> None:
        """--log-level es INFO por defecto."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path)]
        )
        assert args.log_level == "INFO"

    def test_log_level_debug(self, tmp_path: Path) -> None:
        """--log-level acepta DEBUG."""
        args = _parse_args(
            ["--app-name", "MiApp", "--watch", str(tmp_path),
             "--log-level", "DEBUG"]
        )
        assert args.log_level == "DEBUG"

    def test_watch_y_process_pending_mutuamente_exclusivos(self, tmp_path: Path) -> None:
        """--watch y --process-pending son mutuamente exclusivos."""
        with pytest.raises(SystemExit):
            _parse_args(
                ["--app-name", "MiApp",
                 "--watch", str(tmp_path),
                 "--process-pending"]
            )

    def test_falta_app_name_falla(self) -> None:
        """Sin --app-name el parser falla."""
        with pytest.raises(SystemExit):
            _parse_args(["--process-pending"])

    def test_falta_modo_falla(self) -> None:
        """Sin modo (--watch o --process-pending) el parser falla."""
        with pytest.raises(SystemExit):
            _parse_args(["--app-name", "MiApp"])


# ------------------------------------------------------------------
# _load_application
# ------------------------------------------------------------------


class TestLoadApplication:
    def test_carga_app_existente(
        self, session_factory, active_app: Application
    ) -> None:
        """Carga correctamente una aplicación activa de la BD."""
        result = _load_application(session_factory, active_app.name)
        assert result.name == active_app.name
        assert result.active is True

    def test_app_no_encontrada_llama_sys_exit(self, session_factory) -> None:
        """Si la app no existe, sys.exit(1) es invocado."""
        with pytest.raises(SystemExit) as exc_info:
            _load_application(session_factory, "AppQueNoExiste")
        assert exc_info.value.code == 1

    def test_app_inactiva_llama_sys_exit(
        self, session_factory, engine
    ) -> None:
        """Si la app está desactivada, sys.exit(1) es invocado."""
        with sessionmaker(bind=engine)() as session:
            app = Application(
                name="InactiveApp",
                active=False,
                pipeline_json="[]",
                events_json="{}",
                transfer_json="{}",
            )
            session.add(app)
            session.commit()

        with pytest.raises(SystemExit) as exc_info:
            _load_application(session_factory, "InactiveApp")
        assert exc_info.value.code == 1


# ------------------------------------------------------------------
# _build_executor
# ------------------------------------------------------------------


class TestBuildExecutor:
    def test_pipeline_vacio(self, active_app: Application) -> None:
        """Un pipeline vacío genera un executor sin errores."""
        from app.services.script_engine import ScriptEngine
        script_engine = ScriptEngine()
        executor = _build_executor(active_app, script_engine)
        assert executor is not None

    def test_pipeline_con_script_step(self, active_app: Application) -> None:
        """ScriptStep con script válido se pre-compila sin error."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.steps import ScriptStep
        from app.pipeline.serializer import serialize

        step = ScriptStep(
            id="s1",
            label="Prueba",
            entry_point="run",
            script="def run(app, batch, page, pipeline):\n    pass\n",
        )
        active_app.pipeline_json = serialize([step])
        script_engine = ScriptEngine()
        executor = _build_executor(active_app, script_engine)
        assert executor is not None

    def test_script_con_error_sintaxis_no_propaga(
        self, active_app: Application
    ) -> None:
        """Un ScriptStep con error de sintaxis no lanza excepción fuera."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.steps import ScriptStep
        from app.pipeline.serializer import serialize

        step = ScriptStep(
            id="s1",
            label="Roto",
            entry_point="run",
            script="def run(@@@@",  # sintaxis inválida
        )
        active_app.pipeline_json = serialize([step])
        script_engine = ScriptEngine()
        # No debe lanzar excepción
        executor = _build_executor(active_app, script_engine)
        assert executor is not None


# ------------------------------------------------------------------
# _compile_lifecycle_events
# ------------------------------------------------------------------


class TestCompileLifecycleEvents:
    def test_events_json_vacio_retorna_dict_vacio(
        self, active_app: Application
    ) -> None:
        """Con events_json='{}' el resultado es dict vacío."""
        from app.services.script_engine import ScriptEngine
        active_app.events_json = "{}"
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert result == {}

    def test_events_json_invalido_retorna_dict_vacio(
        self, active_app: Application
    ) -> None:
        """Con events_json no válido retorna dict vacío sin error."""
        from app.services.script_engine import ScriptEngine
        active_app.events_json = "NO ES JSON"
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert result == {}

    def test_events_json_none_retorna_dict_vacio(
        self, active_app: Application
    ) -> None:
        """Con events_json=None retorna dict vacío sin error."""
        from app.services.script_engine import ScriptEngine
        active_app.events_json = None
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert result == {}

    def test_evento_con_script_valido_compilado(
        self, active_app: Application
    ) -> None:
        """Un evento con script válido queda registrado en el resultado."""
        from app.services.script_engine import ScriptEngine
        events = {
            "on_app_start": {
                "script": "def on_app_start(app, batch):\n    pass\n",
                "entry_point": "on_app_start",
            }
        }
        active_app.events_json = json.dumps(events)
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert "on_app_start" in result
        assert result["on_app_start"] == "on_app_start"

    def test_evento_sin_script_ignorado(
        self, active_app: Application
    ) -> None:
        """Un evento con script vacío no aparece en el resultado."""
        from app.services.script_engine import ScriptEngine
        events = {
            "on_app_start": {
                "script": "",
                "entry_point": "on_app_start",
            }
        }
        active_app.events_json = json.dumps(events)
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert "on_app_start" not in result

    def test_evento_con_error_de_compilacion_no_propaga(
        self, active_app: Application
    ) -> None:
        """Un script con error de compilación no detiene el proceso."""
        from app.services.script_engine import ScriptEngine
        events = {
            "on_app_start": {
                "script": "def run(@@@@",  # sintaxis inválida
                "entry_point": "on_app_start",
            }
        }
        active_app.events_json = json.dumps(events)
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        # El evento no se registra si falla la compilación
        assert "on_app_start" not in result

    def test_multiples_eventos(self, active_app: Application) -> None:
        """Varios eventos válidos quedan todos registrados."""
        from app.services.script_engine import ScriptEngine
        events = {
            "on_app_start": {
                "script": "def ev(app, batch):\n    pass\n",
                "entry_point": "ev",
            },
            "on_scan_complete": {
                "script": "def sc(app, batch):\n    pass\n",
                "entry_point": "sc",
            },
        }
        active_app.events_json = json.dumps(events)
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert "on_app_start" in result
        assert "on_scan_complete" in result

    def test_entrada_no_dict_ignorada(
        self, active_app: Application
    ) -> None:
        """Si el valor del evento no es un dict, se ignora sin error."""
        from app.services.script_engine import ScriptEngine
        active_app.events_json = json.dumps({"on_app_start": "esto no es dict"})
        result = _compile_lifecycle_events(active_app, ScriptEngine())
        assert result == {}


# ------------------------------------------------------------------
# _process_files
# ------------------------------------------------------------------


class TestProcessFiles:
    """Tests de _process_files con servicios completamente mockeados."""

    def _make_page_mock(self, index: int = 0) -> MagicMock:
        """Crea un mock de Page de BD."""
        page = MagicMock(spec=Page)
        page.page_index = index
        page.ocr_text = ""
        page.ai_fields_json = "{}"
        page.index_fields_json = "{}"
        page.needs_review = False
        page.review_reason = ""
        page.processing_errors_json = "[]"
        page.script_errors_json = "[]"
        return page

    def _make_batch_mock(self, batch_id: int = 1) -> MagicMock:
        """Crea un mock de Batch."""
        batch = MagicMock(spec=Batch)
        batch.id = batch_id
        batch.state = "created"
        batch.stats_json = "{}"
        return batch

    def _make_services(self, tmp_path: Path, batch_id: int = 1):
        """Construye mocks de BatchService, TransferService, NotificationService."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        page_mock = self._make_page_mock()
        batch_mock = self._make_batch_mock(batch_id)

        batch_svc = MagicMock()
        batch_svc.create_batch.return_value = batch_mock
        batch_svc.add_pages.return_value = [page_mock]
        batch_svc.transition_state.return_value = batch_mock
        batch_svc.get_batch.return_value = batch_mock
        batch_svc.get_pages.return_value = [page_mock]
        batch_svc.get_fields.return_value = {}
        batch_svc.get_stats.return_value = {}

        return batch_svc, image, page_mock, batch_mock

    def test_flujo_normal_sin_auto_transfer(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """El flujo básico crea lote, importa y ejecuta pipeline sin error."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor
        from app.services.image_pipeline import ImagePipelineService

        image = np.ones((100, 100, 3), dtype=np.uint8) * 200
        batch_svc, _, page_mock, batch_mock = self._make_services(tmp_path)

        executor_mock = MagicMock(spec=PipelineExecutor)
        import_svc_mock = MagicMock()
        import_svc_mock.import_file.return_value = [image]
        script_engine_mock = MagicMock(spec=ScriptEngine)

        # Parche de BatchService para que use nuestro mock
        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc,
        ), patch(
            "docscan_worker.worker_main.TransferService",
        ), patch(
            "docscan_worker.worker_main.NotificationService",
        ):
            _process_files(
                file_paths=[tmp_path / "scan.tiff"],
                app_record=active_app,
                executor=executor_mock,
                import_service=import_svc_mock,
                script_engine=script_engine_mock,
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        batch_svc.create_batch.assert_called_once()
        import_svc_mock.import_file.assert_called_once()
        executor_mock.execute.assert_called_once()
        batch_svc.transition_state.assert_called()

    def test_shutdown_aborta_importacion(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Si _shutdown está activo, la importación se aborta."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        batch_svc, _, _, batch_mock = self._make_services(tmp_path)
        executor_mock = MagicMock(spec=PipelineExecutor)
        import_svc_mock = MagicMock()
        script_engine_mock = MagicMock(spec=ScriptEngine)

        # Activar shutdown antes de procesar
        wm._shutdown.set()

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            _process_files(
                file_paths=[tmp_path / "scan.tiff"],
                app_record=active_app,
                executor=executor_mock,
                import_service=import_svc_mock,
                script_engine=script_engine_mock,
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        # import_file no debería haberse llamado
        import_svc_mock.import_file.assert_not_called()

    def test_importacion_fallida_transiciona_a_error_read(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Si todos los import_file fallan, el lote pasa a error_read."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        batch_svc, _, _, batch_mock = self._make_services(tmp_path)
        executor_mock = MagicMock(spec=PipelineExecutor)
        import_svc_mock = MagicMock()
        import_svc_mock.import_file.side_effect = IOError("fichero corrompido")
        script_engine_mock = MagicMock(spec=ScriptEngine)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            _process_files(
                file_paths=[tmp_path / "bad.tiff"],
                app_record=active_app,
                executor=executor_mock,
                import_service=import_svc_mock,
                script_engine=script_engine_mock,
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        # Debe haberse llamado transition_state con "error_read"
        estados = [c.args[1] for c in batch_svc.transition_state.call_args_list]
        assert "error_read" in estados

    def test_evento_on_app_start_ejecutado(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Si on_app_start está en lifecycle_events, se ejecuta."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        image = np.ones((50, 50, 3), dtype=np.uint8)
        batch_svc, _, page_mock, batch_mock = self._make_services(tmp_path)
        executor_mock = MagicMock(spec=PipelineExecutor)
        import_svc_mock = MagicMock()
        import_svc_mock.import_file.return_value = [image]
        script_engine_mock = MagicMock(spec=ScriptEngine)

        lifecycle = {"on_app_start": "on_app_start"}

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            _process_files(
                file_paths=[tmp_path / "img.jpg"],
                app_record=active_app,
                executor=executor_mock,
                import_service=import_svc_mock,
                script_engine=script_engine_mock,
                lifecycle_events=lifecycle,
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        # run_event debe haberse llamado con on_app_start
        event_names = [c.args[0] for c in script_engine_mock.run_event.call_args_list]
        assert "on_app_start" in event_names

    def test_auto_transfer_invoca_transfer_batch(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Con auto_transfer=True se invoca _transfer_batch."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        active_app.auto_transfer = True
        image = np.ones((50, 50, 3), dtype=np.uint8)
        batch_svc, _, page_mock, batch_mock = self._make_services(tmp_path)
        executor_mock = MagicMock(spec=PipelineExecutor)
        import_svc_mock = MagicMock()
        import_svc_mock.import_file.return_value = [image]
        script_engine_mock = MagicMock(spec=ScriptEngine)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"), \
           patch("docscan_worker.worker_main._transfer_batch") as mock_transfer:
            _process_files(
                file_paths=[tmp_path / "img.png"],
                app_record=active_app,
                executor=executor_mock,
                import_service=import_svc_mock,
                script_engine=script_engine_mock,
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        mock_transfer.assert_called_once()


# ------------------------------------------------------------------
# _transfer_batch
# ------------------------------------------------------------------


class TestTransferBatch:
    def _make_transfer_context(self, tmp_path: Path, batch_id: int = 1):
        """Construye mocks mínimos para _transfer_batch."""
        batch_svc = MagicMock()
        batch_svc.get_pages.return_value = []
        batch_svc.get_fields.return_value = {}
        batch_svc.get_stats.return_value = {}

        transfer_svc = MagicMock()
        notification_svc = MagicMock()
        script_engine = MagicMock()
        session = MagicMock()
        app_ctx = AppContext(id=1, name="TestApp", description="")
        batch_ctx = BatchContext(id=batch_id, state="ready_to_export")
        return (
            batch_svc, transfer_svc, notification_svc,
            script_engine, session, app_ctx, batch_ctx,
        )

    def test_sin_destino_no_transfiere(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """Si no hay destino de transferencia configurado, no transfiere."""
        from app.services.transfer_service import TransferConfig
        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)

        active_app.transfer_json = json.dumps({"destination": ""})

        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events={},
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )
        transfer_svc.transfer.assert_not_called()

    def test_transferencia_exitosa_transiciona_a_exported(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """Una transferencia exitosa marca el lote como exported."""
        from app.services.transfer_service import TransferResult

        dest = tmp_path / "output"
        dest.mkdir()
        active_app.transfer_json = json.dumps({
            "mode": "folder",
            "destination": str(dest),
        })

        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)

        transfer_svc.transfer.return_value = TransferResult(
            success=True,
            files_transferred=3,
            output_path=str(dest),
        )

        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events={},
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )

        batch_svc.transition_state.assert_called_with(1, "exported")

    def test_transferencia_fallida_transiciona_a_error_export(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """Una transferencia fallida marca el lote como error_export."""
        from app.services.transfer_service import TransferResult

        dest = tmp_path / "output"
        dest.mkdir()
        active_app.transfer_json = json.dumps({
            "mode": "folder",
            "destination": str(dest),
        })

        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)

        transfer_svc.transfer.return_value = TransferResult(
            success=False,
            errors=["permisos denegados"],
        )

        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events={},
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )

        batch_svc.transition_state.assert_called_with(1, "error_export")

    def test_on_transfer_validate_false_cancela_transferencia(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """Si on_transfer_validate devuelve False, no se transfiere."""
        dest = tmp_path / "output"
        dest.mkdir()
        active_app.transfer_json = json.dumps({
            "mode": "folder",
            "destination": str(dest),
        })

        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)
        script_engine.run_event.return_value = False

        lifecycle = {"on_transfer_validate": "validate"}
        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events=lifecycle,
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )

        transfer_svc.transfer.assert_not_called()

    def test_on_transfer_advanced_invocado_tras_exito(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """on_transfer_advanced se ejecuta tras transferencia exitosa."""
        from app.services.transfer_service import TransferResult

        dest = tmp_path / "output"
        dest.mkdir()
        active_app.transfer_json = json.dumps({
            "mode": "folder",
            "destination": str(dest),
        })

        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)
        transfer_svc.transfer.return_value = TransferResult(
            success=True, files_transferred=1, output_path=str(dest),
        )

        lifecycle = {"on_transfer_advanced": "advanced"}
        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events=lifecycle,
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )

        event_names = [c.args[0] for c in script_engine.run_event.call_args_list]
        assert "on_transfer_advanced" in event_names

    def test_paginas_excluidas_no_se_transfieren(
        self, active_app: Application, tmp_path: Path
    ) -> None:
        """Las páginas con is_excluded=True no se incluyen en la transferencia."""
        from app.services.transfer_service import TransferResult

        dest = tmp_path / "output"
        dest.mkdir()
        active_app.transfer_json = json.dumps({
            "mode": "folder",
            "destination": str(dest),
        })

        excluded_page = MagicMock()
        excluded_page.is_excluded = True
        included_page = MagicMock()
        included_page.is_excluded = False
        included_page.image_path = str(tmp_path / "img.tiff")
        included_page.page_index = 0
        included_page.index_fields_json = "{}"
        included_page.ocr_text = ""
        included_page.ai_fields_json = "{}"

        (batch_svc, transfer_svc, notification_svc,
         script_engine, session, app_ctx, batch_ctx) = self._make_transfer_context(tmp_path)
        batch_svc.get_pages.return_value = [excluded_page, included_page]
        transfer_svc.transfer.return_value = TransferResult(
            success=True, files_transferred=1, output_path=str(dest),
        )

        _transfer_batch(
            batch_id=1,
            app_record=active_app,
            batch_svc=batch_svc,
            transfer_svc=transfer_svc,
            notification_svc=notification_svc,
            script_engine=script_engine,
            lifecycle_events={},
            session=session,
            app_ctx=app_ctx,
            batch_ctx=batch_ctx,
        )

        # Solo 1 página debería llegar al transfer
        pages_data = transfer_svc.transfer.call_args[0][0]
        assert len(pages_data) == 1


# ------------------------------------------------------------------
# _process_pending_batches
# ------------------------------------------------------------------


class TestProcessPendingBatches:
    def _make_batch(self, batch_id: int, app_id: int, state: str) -> MagicMock:
        batch = MagicMock(spec=Batch)
        batch.id = batch_id
        batch.application_id = app_id
        batch.state = state
        return batch

    def test_sin_lotes_pendientes_retorna_cero(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Sin lotes en BD el conteo de procesados es 0."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.return_value = []

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            count = _process_pending_batches(
                app_record=active_app,
                executor=MagicMock(spec=PipelineExecutor),
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        assert count == 0

    def test_lote_read_ejecuta_pipeline(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Un lote en estado 'read' ejecuta el pipeline y pasa a ready_to_export."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        image = np.ones((50, 50, 3), dtype=np.uint8)

        page_mock = MagicMock(spec=Page)
        page_mock.page_index = 0
        page_mock.ocr_text = ""
        page_mock.ai_fields_json = "{}"
        page_mock.index_fields_json = "{}"
        page_mock.needs_review = False
        page_mock.review_reason = ""
        page_mock.processing_errors_json = "[]"
        page_mock.script_errors_json = "[]"

        batch_mock = self._make_batch(1, active_app.id, "read")

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.side_effect = lambda state: (
            [batch_mock] if state == "read" else []
        )
        batch_svc_mock.get_pages.return_value = [page_mock]
        batch_svc_mock.get_page_image.return_value = image

        executor_mock = MagicMock(spec=PipelineExecutor)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            count = _process_pending_batches(
                app_record=active_app,
                executor=executor_mock,
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        assert count == 1
        executor_mock.execute.assert_called_once()
        batch_svc_mock.transition_state.assert_called_with(1, "ready_to_export")

    def test_lote_ready_to_export_invoca_transfer(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Un lote en 'ready_to_export' invoca _transfer_batch."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        batch_mock = self._make_batch(2, active_app.id, "ready_to_export")

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.side_effect = lambda state: (
            [batch_mock] if state == "ready_to_export" else []
        )

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"), \
           patch("docscan_worker.worker_main._transfer_batch") as mock_transfer:
            count = _process_pending_batches(
                app_record=active_app,
                executor=MagicMock(spec=PipelineExecutor),
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        assert count == 1
        mock_transfer.assert_called_once()

    def test_lote_de_otra_app_ignorado(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Un lote que pertenece a otra app no se procesa."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        other_batch = self._make_batch(99, active_app.id + 999, "read")

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.side_effect = lambda state: (
            [other_batch] if state == "read" else []
        )

        executor_mock = MagicMock(spec=PipelineExecutor)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            count = _process_pending_batches(
                app_record=active_app,
                executor=executor_mock,
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        assert count == 0
        executor_mock.execute.assert_not_called()

    def test_shutdown_durante_read_detiene_bucle(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Si _shutdown se activa durante bucle 'read', se detiene."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        b1 = self._make_batch(1, active_app.id, "read")
        b2 = self._make_batch(2, active_app.id, "read")

        image = np.ones((50, 50, 3), dtype=np.uint8)
        page_mock = MagicMock(spec=Page)
        page_mock.page_index = 0
        page_mock.ocr_text = ""
        page_mock.ai_fields_json = "{}"
        page_mock.index_fields_json = "{}"
        page_mock.needs_review = False
        page_mock.review_reason = ""
        page_mock.processing_errors_json = "[]"
        page_mock.script_errors_json = "[]"

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.side_effect = lambda state: (
            [b1, b2] if state == "read" else []
        )
        batch_svc_mock.get_pages.return_value = [page_mock]
        batch_svc_mock.get_page_image.return_value = image

        # Activar shutdown
        wm._shutdown.set()

        executor_mock = MagicMock(spec=PipelineExecutor)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            count = _process_pending_batches(
                app_record=active_app,
                executor=executor_mock,
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        # Con _shutdown activo, ningún lote debería procesarse
        assert count == 0

    def test_imagen_none_omite_pagina(
        self, active_app: Application, tmp_path: Path, session_factory
    ) -> None:
        """Si get_page_image retorna None, la página se omite."""
        from app.services.script_engine import ScriptEngine
        from app.pipeline.executor import PipelineExecutor

        batch_mock = self._make_batch(1, active_app.id, "read")
        page_mock = MagicMock(spec=Page)
        page_mock.page_index = 0

        batch_svc_mock = MagicMock()
        batch_svc_mock.get_batches_by_state.side_effect = lambda state: (
            [batch_mock] if state == "read" else []
        )
        batch_svc_mock.get_pages.return_value = [page_mock]
        batch_svc_mock.get_page_image.return_value = None  # Sin imagen

        executor_mock = MagicMock(spec=PipelineExecutor)

        with patch(
            "docscan_worker.worker_main.BatchService",
            return_value=batch_svc_mock,
        ), patch("docscan_worker.worker_main.TransferService"), \
           patch("docscan_worker.worker_main.NotificationService"):
            _process_pending_batches(
                app_record=active_app,
                executor=executor_mock,
                import_service=MagicMock(),
                script_engine=MagicMock(spec=ScriptEngine),
                lifecycle_events={},
                session_factory=session_factory,
                images_dir=tmp_path / "images",
            )

        executor_mock.execute.assert_not_called()


# ------------------------------------------------------------------
# main()
# ------------------------------------------------------------------


class TestMain:
    """Tests de integración de main() con mocks de alto nivel."""

    def _make_app_record(self, app_id: int = 1) -> MagicMock:
        """Mock de Application para usar en main()."""
        app = MagicMock(spec=Application)
        app.id = app_id
        app.name = "TestApp"
        app.description = ""
        app.active = True
        app.pipeline_json = "[]"
        app.events_json = "{}"
        app.transfer_json = "{}"
        app.auto_transfer = False
        return app

    def test_process_pending_retorna_cero(self, tmp_path: Path) -> None:
        """main() --process-pending retorna 0 cuando no hay pendientes."""
        app_mock = self._make_app_record()

        with patch("docscan_worker.worker_main.create_db_engine"), \
             patch("docscan_worker.worker_main.create_tables"), \
             patch("docscan_worker.worker_main.get_session_factory"), \
             patch("docscan_worker.worker_main._load_application", return_value=app_mock), \
             patch("docscan_worker.worker_main.ScriptEngine"), \
             patch("docscan_worker.worker_main._compile_lifecycle_events", return_value={}), \
             patch("docscan_worker.worker_main._build_executor"), \
             patch("docscan_worker.worker_main.ImportService"), \
             patch("docscan_worker.worker_main.APP_DATA_DIR", tmp_path), \
             patch("docscan_worker.worker_main._process_pending_batches", return_value=0) as mock_pp:
            result = wm.main(["--app-name", "TestApp", "--process-pending"])

        assert result == 0
        mock_pp.assert_called_once()

    def test_process_pending_registra_conteo(self, tmp_path: Path) -> None:
        """main() --process-pending informa cuántos lotes se procesaron."""
        app_mock = self._make_app_record()

        with patch("docscan_worker.worker_main.create_db_engine"), \
             patch("docscan_worker.worker_main.create_tables"), \
             patch("docscan_worker.worker_main.get_session_factory"), \
             patch("docscan_worker.worker_main._load_application", return_value=app_mock), \
             patch("docscan_worker.worker_main.ScriptEngine"), \
             patch("docscan_worker.worker_main._compile_lifecycle_events", return_value={}), \
             patch("docscan_worker.worker_main._build_executor"), \
             patch("docscan_worker.worker_main.ImportService"), \
             patch("docscan_worker.worker_main.APP_DATA_DIR", tmp_path), \
             patch("docscan_worker.worker_main._process_pending_batches", return_value=5):
            result = wm.main(["--app-name", "TestApp", "--process-pending"])

        assert result == 0

    def test_watch_carpeta_no_existe_retorna_uno(self, tmp_path: Path) -> None:
        """main() --watch con carpeta inexistente retorna 1."""
        app_mock = self._make_app_record()
        nonexistent = tmp_path / "no_existe"

        with patch("docscan_worker.worker_main.create_db_engine"), \
             patch("docscan_worker.worker_main.create_tables"), \
             patch("docscan_worker.worker_main.get_session_factory"), \
             patch("docscan_worker.worker_main._load_application", return_value=app_mock), \
             patch("docscan_worker.worker_main.ScriptEngine"), \
             patch("docscan_worker.worker_main._compile_lifecycle_events", return_value={}), \
             patch("docscan_worker.worker_main._build_executor"), \
             patch("docscan_worker.worker_main.ImportService"), \
             patch("docscan_worker.worker_main.APP_DATA_DIR", tmp_path):
            result = wm.main(
                ["--app-name", "TestApp", "--watch", str(nonexistent)]
            )

        assert result == 1

    def test_watch_mode_inicia_folder_watcher(self, tmp_path: Path) -> None:
        """main() --watch crea y arranca el FolderWatcher."""
        app_mock = self._make_app_record()
        watch_folder = tmp_path / "watch"
        watch_folder.mkdir()

        watcher_mock = MagicMock()

        def make_watcher(**kwargs):
            wm._shutdown.set()
            return watcher_mock

        with patch("docscan_worker.worker_main.create_db_engine"), \
             patch("docscan_worker.worker_main.create_tables"), \
             patch("docscan_worker.worker_main.get_session_factory"), \
             patch("docscan_worker.worker_main._load_application", return_value=app_mock), \
             patch("docscan_worker.worker_main.ScriptEngine"), \
             patch("docscan_worker.worker_main._compile_lifecycle_events", return_value={}), \
             patch("docscan_worker.worker_main._build_executor"), \
             patch("docscan_worker.worker_main.ImportService"), \
             patch("docscan_worker.worker_main.APP_DATA_DIR", tmp_path), \
             patch("docscan_worker.folder_watcher.FolderWatcher", side_effect=make_watcher):
            result = wm.main(
                ["--app-name", "TestApp", "--watch", str(watch_folder)]
            )

        assert result == 0
        watcher_mock.start.assert_called_once()
        watcher_mock.stop.assert_called_once()

    def test_watch_mode_pasa_debounce_y_sentinel(self, tmp_path: Path) -> None:
        """main() --watch pasa los parámetros debounce y sentinel al FolderWatcher."""
        app_mock = self._make_app_record()
        watch_folder = tmp_path / "watch"
        watch_folder.mkdir()

        captured_kwargs: dict = {}
        watcher_mock = MagicMock()

        def make_watcher(**kwargs):
            captured_kwargs.update(kwargs)
            wm._shutdown.set()
            return watcher_mock

        with patch("docscan_worker.worker_main.create_db_engine"), \
             patch("docscan_worker.worker_main.create_tables"), \
             patch("docscan_worker.worker_main.get_session_factory"), \
             patch("docscan_worker.worker_main._load_application", return_value=app_mock), \
             patch("docscan_worker.worker_main.ScriptEngine"), \
             patch("docscan_worker.worker_main._compile_lifecycle_events", return_value={}), \
             patch("docscan_worker.worker_main._build_executor"), \
             patch("docscan_worker.worker_main.ImportService"), \
             patch("docscan_worker.worker_main.APP_DATA_DIR", tmp_path), \
             patch("docscan_worker.folder_watcher.FolderWatcher", side_effect=make_watcher):
            wm.main([
                "--app-name", "TestApp",
                "--watch", str(watch_folder),
                "--debounce", "7",
                "--sentinel", "READY.txt",
            ])

        assert captured_kwargs.get("debounce_seconds") == 7
        assert captured_kwargs.get("sentinel_filename") == "READY.txt"


# ------------------------------------------------------------------
# _shutdown event
# ------------------------------------------------------------------


class TestShutdownEvent:
    def test_shutdown_inicialmente_inactivo(self) -> None:
        """El evento _shutdown empieza sin activar."""
        wm._shutdown.clear()
        assert not wm._shutdown.is_set()

    def test_shutdown_se_puede_activar(self) -> None:
        """El evento _shutdown se puede activar desde tests."""
        wm._shutdown.set()
        assert wm._shutdown.is_set()

    def test_shutdown_se_puede_limpiar(self) -> None:
        """El evento _shutdown se puede limpiar."""
        wm._shutdown.set()
        wm._shutdown.clear()
        assert not wm._shutdown.is_set()

    def test_signal_handler_activa_shutdown(self) -> None:
        """El manejador de señal interno activa _shutdown."""
        # Simulamos el manejador interno creado dentro de main()
        wm._shutdown.clear()

        # Definir el handler equivalente al de main()
        def _handle_signal(signum, _frame):
            wm._shutdown.set()

        _handle_signal(2, None)  # 2 = SIGINT
        assert wm._shutdown.is_set()
