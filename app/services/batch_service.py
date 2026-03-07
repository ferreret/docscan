"""Servicio de gestión de lotes.

Orquesta la creación de lotes, añadido de páginas, transiciones
de estado y consultas agregadas.
"""

from __future__ import annotations

import json
import logging
import platform
from getpass import getuser
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.models.batch import Batch, BATCH_STATES
from app.models.page import Page
from app.db.repositories.batch_repo import BatchRepository
from app.db.repositories.page_repo import PageRepository

log = logging.getLogger(__name__)


class BatchService:
    """Servicio de lotes.

    Args:
        session: Sesión SQLAlchemy activa.
        images_dir: Directorio raíz para almacenar imágenes de páginas.
    """

    def __init__(self, session: Session, images_dir: Path) -> None:
        self._session = session
        self._images_dir = images_dir
        self._batch_repo = BatchRepository(session)
        self._page_repo = PageRepository(session)

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------

    def create_batch(
        self,
        application_id: int,
        folder_path: str = "",
        fields: dict[str, str] | None = None,
    ) -> Batch:
        """Crea un lote nuevo en estado 'created'.

        Args:
            application_id: ID de la aplicación.
            folder_path: Ruta de origen (opcional).
            fields: Campos de lote iniciales.

        Returns:
            El lote recién creado.
        """
        batch = Batch(
            application_id=application_id,
            state="created",
            folder_path=folder_path,
            hostname=platform.node(),
            username=getuser(),
            fields_json=json.dumps(fields or {}),
        )
        self._batch_repo.save(batch)
        log.info("Lote %d creado para app %d", batch.id, application_id)
        return batch

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------

    def add_pages(
        self,
        batch_id: int,
        images: list[np.ndarray],
        output_format: str = "tiff",
    ) -> list[Page]:
        """Añade imágenes como páginas al lote.

        Guarda cada imagen en disco y crea los registros Page.

        Args:
            batch_id: ID del lote.
            images: Lista de imágenes (numpy arrays BGR).
            output_format: Formato de salida ('tiff', 'png', 'jpg').

        Returns:
            Lista de páginas creadas.
        """
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise ValueError(f"Lote {batch_id} no encontrado")

        batch_dir = self._batch_dir(batch)
        batch_dir.mkdir(parents=True, exist_ok=True)

        existing_count = self._page_repo.count_by_batch(batch_id)
        pages: list[Page] = []

        ext = f".{output_format.lower().strip('.')}"
        if ext == ".jpeg":
            ext = ".jpg"

        for i, img in enumerate(images):
            page_index = existing_count + i
            filename = f"page_{page_index:04d}{ext}"
            filepath = batch_dir / filename

            cv2.imwrite(str(filepath), img)

            page = Page(
                batch_id=batch_id,
                page_index=page_index,
                image_path=str(filepath),
            )
            pages.append(page)

        self._page_repo.save_all(pages)
        batch.page_count = existing_count + len(images)
        self._session.flush()

        log.info(
            "Añadidas %d páginas al lote %d (total: %d)",
            len(images), batch_id, batch.page_count,
        )
        return pages

    def get_page_image(self, page: Page) -> np.ndarray | None:
        """Carga la imagen de una página desde disco."""
        if not page.image_path:
            return None
        img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
        return img

    def remove_page(self, page_id: int) -> None:
        """Elimina una página y su imagen de disco."""
        page = self._page_repo.get_by_id(page_id)
        if page is None:
            return
        # Eliminar imagen de disco
        path = Path(page.image_path)
        if path.exists():
            path.unlink()
        self._page_repo.delete(page_id)

    def reorder_pages(self, batch_id: int, page_ids: list[int]) -> None:
        """Reordena las páginas según el orden dado de IDs."""
        pages = self._page_repo.get_by_batch(batch_id)
        id_to_page = {p.id: p for p in pages}
        for new_index, pid in enumerate(page_ids):
            if pid in id_to_page:
                id_to_page[pid].page_index = new_index
        self._session.flush()

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def transition_state(self, batch_id: int, new_state: str) -> Batch:
        """Cambia el estado de un lote.

        Args:
            batch_id: ID del lote.
            new_state: Nuevo estado (debe ser uno de BATCH_STATES).

        Returns:
            El lote actualizado.

        Raises:
            ValueError: Si el estado no es válido o el lote no existe.
        """
        if new_state not in BATCH_STATES:
            raise ValueError(
                f"Estado no válido: '{new_state}'. "
                f"Válidos: {BATCH_STATES}"
            )

        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise ValueError(f"Lote {batch_id} no encontrado")

        old_state = batch.state
        batch.state = new_state
        self._session.flush()

        log.info("Lote %d: %s → %s", batch_id, old_state, new_state)
        return batch

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_batch(self, batch_id: int) -> Batch | None:
        return self._batch_repo.get_by_id(batch_id)

    def get_batches_by_app(self, app_id: int) -> list[Batch]:
        return self._batch_repo.get_by_application(app_id)

    def get_batches_by_state(self, state: str) -> list[Batch]:
        return self._batch_repo.get_by_state(state)

    def get_pages(self, batch_id: int) -> list[Page]:
        return self._page_repo.get_by_batch(batch_id)

    def get_pages_needing_review(self, batch_id: int) -> list[Page]:
        return self._page_repo.get_needs_review(batch_id)

    def get_stats(self, batch_id: int) -> dict:
        """Devuelve estadísticas del lote."""
        pages = self._page_repo.get_by_batch(batch_id)
        return {
            "total_pages": len(pages),
            "needs_review": sum(1 for p in pages if p.needs_review),
            "excluded": sum(1 for p in pages if p.is_excluded),
            "blank": sum(1 for p in pages if p.is_blank),
            "with_errors": sum(
                1 for p in pages if p.processing_errors_json != "[]"
            ),
        }

    # ------------------------------------------------------------------
    # Campos de lote
    # ------------------------------------------------------------------

    def get_fields(self, batch_id: int) -> dict[str, str]:
        """Devuelve los campos del lote."""
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            return {}
        return json.loads(batch.fields_json)

    def set_fields(self, batch_id: int, fields: dict[str, str]) -> None:
        """Establece los campos del lote."""
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise ValueError(f"Lote {batch_id} no encontrado")
        batch.fields_json = json.dumps(fields)
        self._session.flush()

    # ------------------------------------------------------------------
    # Eliminación
    # ------------------------------------------------------------------

    def delete_batch(self, batch_id: int) -> None:
        """Elimina un lote y sus imágenes de disco."""
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            return

        # Eliminar directorio de imágenes
        batch_dir = self._batch_dir(batch)
        if batch_dir.exists():
            for f in batch_dir.iterdir():
                if f.is_file():
                    f.unlink()
            try:
                batch_dir.rmdir()
            except OSError:
                log.warning("No se pudo eliminar directorio: %s", batch_dir)

        self._batch_repo.delete(batch_id)
        log.info("Lote %d eliminado", batch_id)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _batch_dir(self, batch: Batch) -> Path:
        """Directorio de imágenes del lote."""
        return self._images_dir / f"app_{batch.application_id}" / f"batch_{batch.id}"
