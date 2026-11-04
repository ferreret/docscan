"""Worker de escaneo/importación en hilo secundario.

Ejecuta la adquisición de imágenes (escáner o importación) sin bloquear
la UI. Emite una señal por cada página adquirida para procesamiento
inmediato en el RecognitionWorker.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

from app.services.scanner_service import ScanIncompleteError

log = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Hilo de adquisición de imágenes.

    Signals:
        page_acquired: (page_index, image, source_path) por cada página.
        finished_scanning: total de páginas adquiridas. **Solo** si la
            adquisición terminó entera.
        cancelled: páginas emitidas antes de interrumpir. Excluyente con
            finished_scanning: quien cancela no recibe "terminado".
        error_occurred: mensaje de error. Si el escáner falla a mitad de
            lote, llega después de las páginas ya capturadas y en lugar
            de finished_scanning.
    """

    page_acquired = Signal(int, object, str)  # (index, np.ndarray, source_path)
    finished_scanning = Signal(int)
    cancelled = Signal(int)
    error_occurred = Signal(str)

    def __init__(
        self,
        mode: str,
        source: str | list[str] = "",
        scanner: Any = None,
        import_service: Any = None,
        scan_config: Any = None,
        dpi: int = 300,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._emitidas = 0
        self._mode = mode  # "scanner", "import_file", "import_files", "import_folder", "import_pdf"
        self._source = source
        self._scanner = scanner
        self._import_service = import_service
        self._scan_config = scan_config
        self._dpi = dpi

    def run(self) -> None:
        """Ejecuta la adquisición según el modo configurado.

        Al interrumpirse emite ``cancelled`` con las páginas realmente
        entregadas, nunca ``finished_scanning``: informar del total
        completo tras una cancelación hace creer al consumidor que tiene
        páginas que jamás le llegaron.

        Con escáner, las páginas se emiten en cuanto el backend las entrega
        (si lo admite) y cancelar **conserva** las ya capturadas: el papel
        ya ha pasado por el escáner (FlexibarNET10 v1.27).
        """
        self._emitidas = 0
        error = ""
        try:
            try:
                results = self._acquire()
            except ScanIncompleteError as e:
                # Atasco o doble alimentación a mitad de lote: las páginas
                # ya capturadas se entregan, pero el lote no está completo.
                results = [(img, "") for img in e.images]
                error = str(e)
            if self._mode == "scanner":
                # Las que ya llegaron por on_page no se repiten.
                for img, src in results[self._emitidas :]:
                    self._emit(img, src)
                if self.isInterruptionRequested():
                    log.info(
                        "Escaneo cancelado: %d páginas conservadas", self._emitidas
                    )
                    self.cancelled.emit(self._emitidas)
                    return
                results = []
            for img, src in results:
                if self.isInterruptionRequested():
                    log.info(
                        "Importación interrumpida en la página %d de %d",
                        self._emitidas,
                        len(results),
                    )
                    self.cancelled.emit(self._emitidas)
                    return
                self._emit(img, src)
            if error:
                self.error_occurred.emit(error)
                return
            self.finished_scanning.emit(self._emitidas)
        except Exception as e:
            log.error("Error en ScanWorker: %s", e)
            self.error_occurred.emit(str(e))

    def _emit(self, image: np.ndarray, source_path: str) -> None:
        """Entrega una página y la cuenta."""
        self.page_acquired.emit(self._emitidas, image, source_path)
        self._emitidas += 1

    def _acquire(self) -> list[tuple[np.ndarray, str]]:
        """Delega la adquisición al servicio correspondiente.

        Returns:
            Lista de tuplas (imagen, ruta_origen). La ruta es vacía
            para páginas procedentes del escáner.
        """
        match self._mode:
            case "scanner":
                if self._scanner is None:
                    raise RuntimeError("No hay escáner configurado")
                images = self._scanner.acquire(
                    self._source,
                    self._scan_config,
                    on_page=lambda img: self._emit(img, ""),
                    should_stop=self.isInterruptionRequested,
                )
                return [(img, "") for img in images]
            case "import_file" | "import_pdf":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                source = str(self._source)
                images = self._import_service.import_file(
                    source,
                    dpi=self._dpi,
                )
                return [(img, source) for img in images]
            case "import_files":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                results: list[tuple[np.ndarray, str]] = []
                for path in self._source:
                    images = self._import_service.import_file(
                        path,
                        dpi=self._dpi,
                    )
                    results.extend((img, str(path)) for img in images)
                return results
            case "import_folder":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                images = self._import_service.import_folder(
                    self._source,
                    dpi=self._dpi,
                )
                folder = str(self._source)
                return [(img, folder) for img in images]
            case _:
                raise ValueError(f"Modo de adquisición desconocido: '{self._mode}'")
