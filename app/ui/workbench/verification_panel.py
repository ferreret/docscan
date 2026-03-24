"""Panel de verificación personalizado (plugin UI).

El usuario define una subclase de VerificationPanel en un script Python
(almacenado en events_json["verification_panel"]). El workbench la carga
dinámicamente y la incrusta como pestaña en el panel de metadatos.

WorkbenchAPI es la fachada que el panel usa para comunicarse con el workbench.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import numpy as np
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)


class WorkbenchAPI:
    """Fachada de comunicación entre el panel de verificación y el workbench.

    Proporciona acceso controlado a datos de páginas, lote y navegación.
    No expone el workbench directamente.
    """

    def __init__(
        self,
        session_factory: Any,
        get_pages: Callable[[], list],
        get_batch_id: Callable[[], int | None],
        get_current_index: Callable[[], int],
        navigate_fn: Callable[[int], None],
        log_fn: Callable[[str], None],
        get_batch_fields_fn: Callable[[], dict[str, str]],
        set_batch_field_fn: Callable[[str, str], None],
    ) -> None:
        self._session_factory = session_factory
        self._get_pages = get_pages
        self._get_batch_id = get_batch_id
        self._get_current_index = get_current_index
        self._navigate_fn = navigate_fn
        self._log_fn = log_fn
        self._get_batch_fields_fn = get_batch_fields_fn
        self._set_batch_field_fn = set_batch_field_fn

    # ------------------------------------------------------------------
    # Página actual
    # ------------------------------------------------------------------

    @property
    def current_page(self) -> int:
        """Índice de la página actualmente visible."""
        return self._get_current_index()

    def get_page_count(self) -> int:
        """Número total de páginas en el lote."""
        return len(self._get_pages())

    def navigate_to(self, page_index: int) -> None:
        """Navega a una página por índice."""
        self._navigate_fn(page_index)

    # ------------------------------------------------------------------
    # Datos de página
    # ------------------------------------------------------------------

    def get_page_image(self, page_index: int) -> np.ndarray | None:
        """Carga la imagen de una página desde disco."""
        pages = self._get_pages()
        if page_index < 0 or page_index >= len(pages):
            return None
        path = pages[page_index].image_path
        if not path:
            return None
        import cv2
        return cv2.imread(path, cv2.IMREAD_UNCHANGED)

    def get_page_barcodes(self, page_index: int) -> list[dict[str, Any]]:
        """Devuelve los barcodes de una página como lista de dicts."""
        pages = self._get_pages()
        if page_index < 0 or page_index >= len(pages):
            return []
        page = pages[page_index]
        from app.db.repositories.page_repo import PageRepository
        with self._session_factory() as session:
            repo = PageRepository(session)
            db_page = repo.get_by_id(page.id)
            if db_page is None:
                return []
            return [
                {
                    "value": bc.value,
                    "symbology": bc.symbology,
                    "engine": bc.engine,
                    "role": bc.role,
                    "quality": bc.quality,
                    "x": bc.pos_x, "y": bc.pos_y,
                    "w": bc.pos_w, "h": bc.pos_h,
                }
                for bc in db_page.barcodes
            ]

    def get_page_ocr_text(self, page_index: int) -> str:
        """Devuelve el texto OCR de una página."""
        pages = self._get_pages()
        if page_index < 0 or page_index >= len(pages):
            return ""
        return pages[page_index].ocr_text or ""

    def get_page_fields(self, page_index: int) -> dict[str, Any]:
        """Devuelve los campos de indexación de una página."""
        pages = self._get_pages()
        if page_index < 0 or page_index >= len(pages):
            return {}
        try:
            return json.loads(pages[page_index].index_fields_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_page_field(
        self, page_index: int, name: str, value: Any,
    ) -> None:
        """Establece un campo de indexación en una página (persiste en BD)."""
        pages = self._get_pages()
        if page_index < 0 or page_index >= len(pages):
            return
        page = pages[page_index]
        from app.db.repositories.page_repo import PageRepository
        with self._session_factory() as session:
            repo = PageRepository(session)
            db_page = repo.get_by_id(page.id)
            if db_page is None:
                return
            try:
                fields = json.loads(db_page.index_fields_json or "{}")
            except (json.JSONDecodeError, TypeError):
                fields = {}
            fields[name] = value
            merged_json = json.dumps(fields, ensure_ascii=False)
            db_page.index_fields_json = merged_json
            session.commit()
        # Actualizar cache local
        page.index_fields_json = merged_json

    # ------------------------------------------------------------------
    # Lote
    # ------------------------------------------------------------------

    def get_batch_fields(self) -> dict[str, str]:
        """Devuelve los campos del lote actual."""
        return self._get_batch_fields_fn()

    def set_batch_field(self, name: str, value: str) -> None:
        """Establece un campo del lote (persiste en BD)."""
        self._set_batch_field_fn(name, value)

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        """Envía un mensaje al panel de log del workbench."""
        self._log_fn(message)


class VerificationPanel(QWidget):
    """Clase base para paneles de verificación personalizados.

    El usuario extiende esta clase en un script Python y define:
    - setup_ui(): construye la interfaz gráfica del panel
    - on_page_changed(page_index): al navegar a otra página
    - on_pipeline_completed(page_index): al terminar el pipeline de una página
    - on_batch_loaded(): al abrir/crear un lote
    - validate_page(page_index) -> (bool, str): valida una página individual
    - validate() -> (bool, str): validación global antes de transferir
    - cleanup(): al cerrar el workbench

    Antes de transferir se llama a validate_page() para cada página y
    después a validate() para validación global del lote.

    Ejemplo:
        class MiPanel(VerificationPanel):
            def setup_ui(self):
                from PySide6.QtWidgets import QVBoxLayout, QLabel
                layout = QVBoxLayout(self)
                self.label = QLabel("Esperando...")
                layout.addWidget(self.label)

            def on_page_changed(self, page_index):
                fields = self.api.get_page_fields(page_index)
                self.label.setText(f"NIF: {fields.get('nif', '—')}")

            def validate_page(self, page_index):
                fields = self.api.get_page_fields(page_index)
                if not fields.get("nif"):
                    return False, f"Página {page_index + 1}: NIF obligatorio"
                return True, ""

            def validate(self):
                # Validación global del lote
                return True, ""
    """

    def __init__(self, api: WorkbenchAPI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api = api
        self.setup_ui()

    def setup_ui(self) -> None:
        """Construye la interfaz gráfica. Sobreescribir en la subclase."""
        pass

    def on_page_changed(self, page_index: int) -> None:
        """Se invoca al navegar a otra página."""
        pass

    def on_pipeline_completed(self, page_index: int) -> None:
        """Se invoca al completar el pipeline de una página."""
        pass

    def on_batch_loaded(self) -> None:
        """Se invoca al cargar o crear un lote."""
        pass

    def validate_page(self, page_index: int) -> tuple[bool, str]:
        """Valida una página individual. Se llama para cada página antes de transferir."""
        return True, ""

    def validate(self) -> tuple[bool, str]:
        """Validación global del lote antes de transferir (después de validate_page)."""
        return True, ""

    def cleanup(self) -> None:
        """Limpieza al cerrar el workbench."""
        pass
