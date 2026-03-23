"""Worker de escaneo/importación en hilo secundario.

Ejecuta la adquisición de imágenes (escáner o importación) sin bloquear
la UI. Emite una señal por cada página adquirida para procesamiento
inmediato en el RecognitionWorker.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Hilo de adquisición de imágenes.

    Signals:
        page_acquired: (page_index, image, source_path) por cada página.
        finished_scanning: total de páginas adquiridas.
        error_occurred: mensaje de error.
    """

    page_acquired = Signal(int, object, str)  # (index, np.ndarray, source_path)
    finished_scanning = Signal(int)
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
        self._mode = mode  # "scanner", "import_file", "import_files", "import_folder", "import_pdf"
        self._source = source
        self._scanner = scanner
        self._import_service = import_service
        self._scan_config = scan_config
        self._dpi = dpi

    def run(self) -> None:
        """Ejecuta la adquisición según el modo configurado."""
        try:
            results = self._acquire()
            for i, (img, src) in enumerate(results):
                if self.isInterruptionRequested():
                    log.info("Escaneo interrumpido en página %d", i)
                    break
                self.page_acquired.emit(i, img, src)
            self.finished_scanning.emit(len(results))
        except Exception as e:
            log.error("Error en ScanWorker: %s", e)
            self.error_occurred.emit(str(e))

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
                images = self._scanner.acquire(self._source, self._scan_config)
                return [(img, "") for img in images]
            case "import_file" | "import_pdf":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                source = str(self._source)
                images = self._import_service.import_file(
                    source, dpi=self._dpi,
                )
                return [(img, source) for img in images]
            case "import_files":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                results: list[tuple[np.ndarray, str]] = []
                for path in self._source:
                    images = self._import_service.import_file(
                        path, dpi=self._dpi,
                    )
                    results.extend((img, str(path)) for img in images)
                return results
            case "import_folder":
                if self._import_service is None:
                    raise RuntimeError("ImportService no disponible")
                images = self._import_service.import_folder(
                    self._source, dpi=self._dpi,
                )
                folder = str(self._source)
                return [(img, folder) for img in images]
            case _:
                raise ValueError(f"Modo de adquisición desconocido: '{self._mode}'")
