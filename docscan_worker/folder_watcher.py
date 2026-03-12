"""FolderWatcher — vigila carpeta de entrada y dispara procesamiento.

Combina watchdog (InotifyObserver en Linux) con EventDebouncer para
agrupar ráfagas de archivos, y APScheduler para tareas periódicas.

Triggers soportados (BAT-11):
- Por fichero individual: debounce_seconds=0, cada fichero dispara batch.
- Por lote (timeout de inactividad): debounce_seconds>0, agrupa ráfagas.
- Por fichero centinela: sentinel_filename no vacío, espera a ese fichero.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable

from watchdog.events import (
    FileClosedEvent,
    FileMovedEvent,
    PatternMatchingEventHandler,
)
from watchdog.observers import Observer
from watchdog.utils.event_debouncer import EventDebouncer

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

# Extensiones aceptadas (mismas que ImportService)
WATCHED_PATTERNS = ["*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.bmp", "*.pdf"]

# Tamaño mínimo para considerar un fichero válido
MIN_FILE_SIZE_BYTES = 128


class _DocScanEventHandler(PatternMatchingEventHandler):
    """Handler que filtra por extensión y delega al debouncer.

    Escucha FileClosedEvent (IN_CLOSE_WRITE en Linux) para garantizar
    que el fichero está completamente escrito. Acepta FileMovedEvent
    para cubrir escritura atómica (write-to-tmp + rename).
    """

    def __init__(self, debouncer: EventDebouncer) -> None:
        super().__init__(
            patterns=WATCHED_PATTERNS,
            ignore_patterns=["*.tmp", "*.part", "~*"],
            ignore_directories=True,
            case_sensitive=False,
        )
        self._debouncer = debouncer

    def on_closed(self, event: FileClosedEvent) -> None:
        """IN_CLOSE_WRITE: fichero cerrado tras escritura."""
        log.debug("on_closed: %s", event.src_path)
        self._debouncer.handle_event(event)

    def on_moved(self, event: FileMovedEvent) -> None:
        """Cubre escritura atómica: write-to-tmp + rename."""
        if not event.is_directory:
            log.debug("on_moved: %s -> %s", event.src_path, event.dest_path)
            self._debouncer.handle_event(event)


class _SentinelHandler(PatternMatchingEventHandler):
    """Handler que espera un fichero centinela específico.

    Cuando el centinela aparece, recopila todos los ficheros válidos
    ya presentes en la carpeta y dispara el callback.
    """

    def __init__(
        self,
        sentinel_filename: str,
        watch_folder: Path,
        batch_callback: Callable[[list[Path]], None],
    ) -> None:
        super().__init__(
            patterns=[sentinel_filename],
            ignore_directories=True,
            case_sensitive=False,
        )
        self._sentinel = sentinel_filename
        self._watch_folder = watch_folder
        self._batch_callback = batch_callback

    def on_closed(self, event: FileClosedEvent) -> None:
        self._trigger(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._trigger(event.dest_path)

    def _trigger(self, sentinel_path: str) -> None:
        """Recopila ficheros válidos y dispara el callback."""
        log.info("Fichero centinela detectado: %s", sentinel_path)
        valid_suffixes = {
            ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".pdf",
        }
        files = sorted(
            f for f in self._watch_folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in valid_suffixes
            and f.stat().st_size >= MIN_FILE_SIZE_BYTES
        )
        if files:
            try:
                self._batch_callback(files)
            except Exception as exc:
                log.error("Error en batch_callback (sentinel): %s", exc, exc_info=True)

        # Eliminar el centinela tras procesamiento
        try:
            Path(sentinel_path).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("No se pudo eliminar centinela: %s", exc)


class FolderWatcher:
    """Vigila una carpeta de entrada y dispara un callback por cada lote.

    Args:
        watch_folder: Carpeta a vigilar.
        batch_callback: Función que recibe list[Path] de ficheros listos.
        debounce_seconds: Ventana de silencio antes de disparar el batch.
        sentinel_filename: Si no es vacío, usa modo centinela en vez de
            debounce (ej: "GO.txt", "READY").
        cleanup_interval_seconds: Intervalo para tarea de limpieza.
        cleanup_callback: Función de limpieza periódica (opcional).
        error_retry_interval_seconds: Intervalo para reintento de errores.
        error_retry_callback: Función de reintento (opcional).
    """

    def __init__(
        self,
        watch_folder: Path,
        batch_callback: Callable[[list[Path]], None],
        debounce_seconds: int = 3,
        sentinel_filename: str = "",
        cleanup_interval_seconds: int = 300,
        cleanup_callback: Callable[[], None] | None = None,
        error_retry_interval_seconds: int = 120,
        error_retry_callback: Callable[[], None] | None = None,
    ) -> None:
        self._watch_folder = Path(watch_folder)
        self._batch_callback = batch_callback
        self._sentinel_mode = bool(sentinel_filename)

        # --- Observer ---
        self._observer = Observer()

        if self._sentinel_mode:
            # Modo centinela: espera fichero específico
            self._handler = _SentinelHandler(
                sentinel_filename, self._watch_folder, batch_callback,
            )
            self._debouncer = None
            self._observer.schedule(
                self._handler,
                str(self._watch_folder),
                recursive=False,
            )
        else:
            # Modo debounce: agrupa ficheros por ventana de inactividad
            self._debouncer = EventDebouncer(
                debounce_interval_seconds=max(debounce_seconds, 1),
                events_callback=self._on_debounced_events,
            )
            self._handler = _DocScanEventHandler(self._debouncer)
            self._observer.schedule(
                self._handler,
                str(self._watch_folder),
                recursive=False,
                event_filter=[FileClosedEvent, FileMovedEvent],
            )

        # --- APScheduler ---
        self._scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            },
        )
        if cleanup_callback:
            self._scheduler.add_job(
                cleanup_callback,
                "interval",
                seconds=cleanup_interval_seconds,
                id="folder_cleanup",
                replace_existing=True,
            )
        if error_retry_callback:
            self._scheduler.add_job(
                error_retry_callback,
                "interval",
                seconds=error_retry_interval_seconds,
                id="error_retry",
                replace_existing=True,
            )

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Inicia el observer y el scheduler."""
        if not self._watch_folder.is_dir():
            raise NotADirectoryError(
                f"Carpeta de entrada no existe: {self._watch_folder}"
            )
        if self._debouncer is not None:
            self._debouncer.start()
        self._observer.start()
        self._scheduler.start()
        mode = "centinela" if self._sentinel_mode else "debounce"
        log.info("FolderWatcher iniciado (%s) en: %s", mode, self._watch_folder)

    def stop(self) -> None:
        """Detiene todos los componentes de forma ordenada."""
        log.info("FolderWatcher deteniendo...")
        self._observer.stop()
        self._observer.join(timeout=5)
        if self._debouncer is not None:
            self._debouncer.stop()
        self._scheduler.shutdown(wait=False)
        log.info("FolderWatcher detenido")

    # ------------------------------------------------------------------
    # Callback del debouncer
    # ------------------------------------------------------------------

    def _on_debounced_events(self, events: list) -> None:
        """Recibe la ráfaga agrupada de eventos tras el silencio.

        Extrae rutas únicas, verifica existencia y tamaño, y llama
        al batch_callback.
        """
        valid_suffixes = {
            ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".pdf",
        }
        seen: set[str] = set()
        ready_paths: list[Path] = []

        for event in events:
            raw_path = (
                event.dest_path
                if hasattr(event, "dest_path") and event.dest_path
                else event.src_path
            )
            norm = os.fsdecode(raw_path)
            if norm in seen:
                continue
            seen.add(norm)

            path = Path(norm)
            if not path.is_file():
                continue
            if path.suffix.lower() not in valid_suffixes:
                continue
            try:
                if path.stat().st_size < MIN_FILE_SIZE_BYTES:
                    log.warning("Fichero demasiado pequeño, ignorado: %s", path)
                    continue
            except OSError:
                continue

            ready_paths.append(path)

        if not ready_paths:
            return

        log.info(
            "Lote de %d fichero(s) listo: %s",
            len(ready_paths),
            [p.name for p in ready_paths[:10]],
        )
        try:
            self._batch_callback(ready_paths)
        except Exception as exc:
            log.error("Error en batch_callback: %s", exc, exc_info=True)
