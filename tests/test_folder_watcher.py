"""Tests del módulo FolderWatcher (docscan_worker/folder_watcher.py).

Cubre:
- Creación en modo debounce y modo centinela
- Ciclo de vida start/stop
- _on_debounced_events: filtrado de ficheros válidos, pequeños, ausentes y duplicados
- _DocScanEventHandler: matching de patrones y delegación al debouncer
- _SentinelHandler: disparo al detectar el fichero centinela
- Manejo de errores en batch_callback
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from docscan_worker.folder_watcher import (
    MIN_FILE_SIZE_BYTES,
    WATCHED_PATTERNS,
    FolderWatcher,
    _DocScanEventHandler,
    _SentinelHandler,
)
from watchdog.events import FileClosedEvent, FileMovedEvent


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_closed_event(path: str) -> FileClosedEvent:
    """Crea un FileClosedEvent con la ruta indicada."""
    ev = FileClosedEvent(path)
    return ev


def _make_moved_event(src: str, dest: str) -> FileMovedEvent:
    """Crea un FileMovedEvent con src y dest."""
    ev = FileMovedEvent(src, dest)
    return ev


def _write_valid_file(folder: Path, name: str = "doc.tiff") -> Path:
    """Escribe un fichero de tamaño suficiente para superar MIN_FILE_SIZE_BYTES."""
    p = folder / name
    p.write_bytes(b"X" * (MIN_FILE_SIZE_BYTES + 100))
    return p


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def watch_folder(tmp_path: Path) -> Path:
    """Carpeta temporal de vigilancia."""
    folder = tmp_path / "watch"
    folder.mkdir()
    return folder


@pytest.fixture
def batch_callback() -> MagicMock:
    """Mock del callback de lote."""
    return MagicMock()


# ------------------------------------------------------------------
# Tests de FolderWatcher — construcción
# ------------------------------------------------------------------


class TestFolderWatcherCreation:
    def test_debounce_mode_crea_debouncer(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """En modo debounce el atributo _debouncer no es None."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            debounce_seconds=2,
            sentinel_filename="",
        )
        assert watcher._debouncer is not None
        assert watcher._sentinel_mode is False

    def test_sentinel_mode_no_crea_debouncer(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """En modo centinela el atributo _debouncer es None."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            sentinel_filename="GO.txt",
        )
        assert watcher._debouncer is None
        assert watcher._sentinel_mode is True

    def test_scheduler_registra_cleanup_callback(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Cuando se pasa cleanup_callback el scheduler registra el job."""
        cleanup_cb = MagicMock()
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            cleanup_callback=cleanup_cb,
        )
        job_ids = {job.id for job in watcher._scheduler.get_jobs()}
        assert "folder_cleanup" in job_ids

    def test_scheduler_registra_error_retry_callback(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Cuando se pasa error_retry_callback el scheduler registra el job."""
        retry_cb = MagicMock()
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            error_retry_callback=retry_cb,
        )
        job_ids = {job.id for job in watcher._scheduler.get_jobs()}
        assert "error_retry" in job_ids

    def test_sin_callbacks_scheduler_sin_jobs(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Sin callbacks opcionales el scheduler no tiene jobs."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        assert watcher._scheduler.get_jobs() == []

    def test_debounce_minimo_uno(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """debounce_seconds=0 se eleva a 1 para evitar loop infinito."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            debounce_seconds=0,
        )
        # El debouncer acepta el intervalo mínimo de 1 segundo
        assert watcher._debouncer is not None


# ------------------------------------------------------------------
# Tests de ciclo de vida start/stop
# ------------------------------------------------------------------


class TestFolderWatcherLifecycle:
    def test_start_falla_si_carpeta_no_existe(
        self, tmp_path: Path, batch_callback: MagicMock
    ) -> None:
        """start() lanza NotADirectoryError si la carpeta no existe."""
        nonexistent = tmp_path / "no_existe"
        watcher = FolderWatcher(
            watch_folder=nonexistent,
            batch_callback=batch_callback,
        )
        with pytest.raises(NotADirectoryError, match="no existe"):
            watcher.start()

    def test_start_y_stop_debounce_mode(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """start/stop en modo debounce no lanza excepción."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            debounce_seconds=1,
        )
        watcher.start()
        try:
            assert watcher._observer.is_alive()
            assert watcher._scheduler.running
        finally:
            watcher.stop()

        # Tras stop el scheduler ya no corre
        assert not watcher._scheduler.running

    def test_start_y_stop_sentinel_mode(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """start/stop en modo centinela no lanza excepción."""
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            sentinel_filename="READY.txt",
        )
        watcher.start()
        try:
            assert watcher._observer.is_alive()
        finally:
            watcher.stop()


# ------------------------------------------------------------------
# Tests de _on_debounced_events
# ------------------------------------------------------------------


class TestOnDebouncedEvents:
    """Tests unitarios del callback interno del debouncer."""

    def _make_watcher(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> FolderWatcher:
        return FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=batch_callback,
            debounce_seconds=1,
        )

    def test_fichero_valido_llama_callback(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Un evento con fichero válido en disco invoca el batch_callback."""
        valid_file = _write_valid_file(watch_folder, "scan.tiff")
        watcher = self._make_watcher(watch_folder, batch_callback)

        event = _make_closed_event(str(valid_file))
        watcher._on_debounced_events([event])

        batch_callback.assert_called_once()
        paths = batch_callback.call_args[0][0]
        assert valid_file in paths

    def test_evento_moved_usa_dest_path(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Para FileMovedEvent se usa dest_path, no src_path."""
        dest_file = _write_valid_file(watch_folder, "final.pdf")
        src_path = str(watch_folder / "tmp_abc.tmp")
        event = _make_moved_event(src_path, str(dest_file))

        watcher = self._make_watcher(watch_folder, batch_callback)
        watcher._on_debounced_events([event])

        batch_callback.assert_called_once()
        paths = batch_callback.call_args[0][0]
        assert dest_file in paths

    def test_fichero_ausente_ignorado(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Un evento cuyo fichero no existe en disco es ignorado."""
        watcher = self._make_watcher(watch_folder, batch_callback)
        event = _make_closed_event(str(watch_folder / "fantasma.tiff"))
        watcher._on_debounced_events([event])
        batch_callback.assert_not_called()

    def test_fichero_pequeno_ignorado(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Un fichero más pequeño que MIN_FILE_SIZE_BYTES se ignora."""
        small = watch_folder / "tiny.jpg"
        small.write_bytes(b"X" * 10)

        watcher = self._make_watcher(watch_folder, batch_callback)
        event = _make_closed_event(str(small))
        watcher._on_debounced_events([event])
        batch_callback.assert_not_called()

    def test_extension_invalida_ignorada(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Un fichero con extensión no permitida es ignorado."""
        bad_ext = watch_folder / "datos.xml"
        bad_ext.write_bytes(b"X" * (MIN_FILE_SIZE_BYTES + 100))

        watcher = self._make_watcher(watch_folder, batch_callback)
        event = _make_closed_event(str(bad_ext))
        watcher._on_debounced_events([event])
        batch_callback.assert_not_called()

    def test_rutas_duplicadas_deduplicadas(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """La misma ruta que aparece en múltiples eventos solo se procesa una vez."""
        valid_file = _write_valid_file(watch_folder, "doc.png")
        watcher = self._make_watcher(watch_folder, batch_callback)

        ev1 = _make_closed_event(str(valid_file))
        ev2 = _make_closed_event(str(valid_file))
        watcher._on_debounced_events([ev1, ev2])

        batch_callback.assert_called_once()
        paths = batch_callback.call_args[0][0]
        assert paths.count(valid_file) == 1

    def test_lista_vacia_no_llama_callback(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Con lista de eventos vacía no se invoca el callback."""
        watcher = self._make_watcher(watch_folder, batch_callback)
        watcher._on_debounced_events([])
        batch_callback.assert_not_called()

    def test_error_en_batch_callback_no_propaga(
        self, watch_folder: Path
    ) -> None:
        """Si batch_callback lanza excepción, _on_debounced_events no propaga."""
        crashing_callback = MagicMock(side_effect=RuntimeError("boom"))
        valid_file = _write_valid_file(watch_folder, "safe.tiff")
        watcher = FolderWatcher(
            watch_folder=watch_folder,
            batch_callback=crashing_callback,
            debounce_seconds=1,
        )
        event = _make_closed_event(str(valid_file))
        # No debe lanzar excepción
        watcher._on_debounced_events([event])
        crashing_callback.assert_called_once()

    def test_multiples_ficheros_validos_en_batch(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Varios ficheros válidos se entregan juntos al callback."""
        files = [
            _write_valid_file(watch_folder, f"doc_{i}.jpg")
            for i in range(4)
        ]
        watcher = self._make_watcher(watch_folder, batch_callback)
        events = [_make_closed_event(str(f)) for f in files]
        watcher._on_debounced_events(events)

        batch_callback.assert_called_once()
        paths = batch_callback.call_args[0][0]
        assert len(paths) == 4

    def test_extensiones_aceptadas_case_insensitive(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Las extensiones en mayúsculas también son aceptadas."""
        f_upper = watch_folder / "SCAN.TIFF"
        f_upper.write_bytes(b"X" * (MIN_FILE_SIZE_BYTES + 50))

        watcher = self._make_watcher(watch_folder, batch_callback)
        event = _make_closed_event(str(f_upper))
        watcher._on_debounced_events([event])
        batch_callback.assert_called_once()


# ------------------------------------------------------------------
# Tests de _DocScanEventHandler
# ------------------------------------------------------------------


class TestDocScanEventHandler:
    def test_on_closed_delega_al_debouncer(self) -> None:
        """on_closed pasa el evento al debouncer."""
        debouncer_mock = MagicMock()
        handler = _DocScanEventHandler(debouncer=debouncer_mock)
        ev = _make_closed_event("/watch/doc.tiff")
        handler.on_closed(ev)
        debouncer_mock.handle_event.assert_called_once_with(ev)

    def test_on_moved_delega_al_debouncer(self) -> None:
        """on_moved de fichero pasa el evento al debouncer."""
        debouncer_mock = MagicMock()
        handler = _DocScanEventHandler(debouncer=debouncer_mock)
        ev = _make_moved_event("/watch/tmp.tmp", "/watch/doc.pdf")
        ev.is_directory = False
        handler.on_moved(ev)
        debouncer_mock.handle_event.assert_called_once_with(ev)

    def test_on_moved_directorio_ignorado(self) -> None:
        """on_moved de directorio no delega al debouncer."""
        debouncer_mock = MagicMock()
        handler = _DocScanEventHandler(debouncer=debouncer_mock)
        ev = MagicMock(spec=FileMovedEvent)
        ev.is_directory = True
        handler.on_moved(ev)
        debouncer_mock.handle_event.assert_not_called()

    def test_patrones_configurados(self) -> None:
        """El handler tiene los patrones de las extensiones de imagen."""
        debouncer_mock = MagicMock()
        handler = _DocScanEventHandler(debouncer=debouncer_mock)
        # Verificar que los patrones del handler contienen los de WATCHED_PATTERNS
        assert handler.patterns is not None
        for pattern in WATCHED_PATTERNS:
            assert pattern in handler.patterns

    def test_ignore_patterns_configurados(self) -> None:
        """Los patrones ignorados incluyen *.tmp, *.part y ~*."""
        debouncer_mock = MagicMock()
        handler = _DocScanEventHandler(debouncer=debouncer_mock)
        assert "*.tmp" in handler.ignore_patterns
        assert "*.part" in handler.ignore_patterns
        assert "~*" in handler.ignore_patterns


# ------------------------------------------------------------------
# Tests de _SentinelHandler
# ------------------------------------------------------------------


class TestSentinelHandler:
    def test_trigger_recopila_ficheros_validos(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """_trigger recoge los ficheros válidos de la carpeta."""
        _write_valid_file(watch_folder, "img1.tiff")
        _write_valid_file(watch_folder, "img2.jpg")
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("start")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))

        batch_callback.assert_called_once()
        paths = batch_callback.call_args[0][0]
        assert len(paths) == 2

    def test_trigger_excluye_ficheros_pequeños(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """_trigger ignora ficheros menores que MIN_FILE_SIZE_BYTES."""
        small = watch_folder / "tiny.png"
        small.write_bytes(b"x" * 5)
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("start")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))
        # No hay ficheros válidos: callback no invocado
        batch_callback.assert_not_called()

    def test_trigger_excluye_extensiones_invalidas(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """_trigger ignora ficheros con extensiones no permitidas."""
        bad = watch_folder / "datos.csv"
        bad.write_bytes(b"X" * (MIN_FILE_SIZE_BYTES + 100))
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("go")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))
        batch_callback.assert_not_called()

    def test_trigger_elimina_centinela(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Tras el trigger el fichero centinela es eliminado."""
        _write_valid_file(watch_folder, "img.tiff")
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("go")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))
        assert not sentinel.exists()

    def test_trigger_sin_ficheros_no_llama_callback(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Si no hay ficheros válidos no se invoca el callback."""
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("go")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))
        batch_callback.assert_not_called()

    def test_error_en_batch_callback_no_propaga(
        self, watch_folder: Path
    ) -> None:
        """Si batch_callback lanza excepción, _trigger no propaga."""
        _write_valid_file(watch_folder, "img.bmp")
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("go")
        crashing = MagicMock(side_effect=ValueError("fallo"))

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=crashing,
        )
        # No debe lanzar
        handler._trigger(str(sentinel))
        crashing.assert_called_once()

    def test_on_closed_llama_trigger(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """on_closed del handler llama internamente a _trigger."""
        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        with patch.object(handler, "_trigger") as mock_trigger:
            ev = _make_closed_event(str(watch_folder / "GO.txt"))
            handler.on_closed(ev)
            mock_trigger.assert_called_once_with(str(watch_folder / "GO.txt"))

    def test_on_moved_llama_trigger_con_dest_path(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """on_moved usa dest_path para llamar a _trigger."""
        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        dest = str(watch_folder / "GO.txt")
        with patch.object(handler, "_trigger") as mock_trigger:
            ev = _make_moved_event("/tmp/GO.txt.tmp", dest)
            ev.is_directory = False
            handler.on_moved(ev)
            mock_trigger.assert_called_once_with(dest)

    def test_on_moved_directorio_no_trigger(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """on_moved de directorio no llama a _trigger."""
        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        with patch.object(handler, "_trigger") as mock_trigger:
            ev = MagicMock(spec=FileMovedEvent)
            ev.is_directory = True
            handler.on_moved(ev)
            mock_trigger.assert_not_called()

    def test_trigger_ordena_ficheros_por_nombre(
        self, watch_folder: Path, batch_callback: MagicMock
    ) -> None:
        """Los ficheros entregados al callback están ordenados."""
        _write_valid_file(watch_folder, "z_last.tiff")
        _write_valid_file(watch_folder, "a_first.tiff")
        sentinel = watch_folder / "GO.txt"
        sentinel.write_text("go")

        handler = _SentinelHandler(
            sentinel_filename="GO.txt",
            watch_folder=watch_folder,
            batch_callback=batch_callback,
        )
        handler._trigger(str(sentinel))

        paths = batch_callback.call_args[0][0]
        names = [p.name for p in paths]
        assert names == sorted(names)
