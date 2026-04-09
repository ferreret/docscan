"""Storage de ficheros de páginas (imágenes y PDFs).

Backend filesystem para MVP. Abstracción pensada para migrar a MinIO/S3.

Layout en disco: {base_path}/{tenant_id}/{batch_id}/{uuid}.{ext}
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from web.api.config import get_web_settings

log = logging.getLogger(__name__)


class FilesystemStorage:
    """Almacén de ficheros en disco local.

    Args:
        base_path: Directorio raíz donde se guardan los ficheros.
    """

    def __init__(self, base_path: Path | str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        tenant_id: int,
        batch_id: int,
        content: bytes,
        extension: str,
    ) -> str:
        """Guarda bytes en disco y devuelve la ruta relativa al base_path.

        Args:
            tenant_id: ID del tenant (primer nivel de segregación).
            batch_id: ID del lote (segundo nivel).
            content: Bytes del fichero.
            extension: Extensión sin punto (ej. ``"png"``, ``"jpg"``).

        Returns:
            Ruta relativa (``"{tenant}/{batch}/{uuid}.{ext}"``).
        """
        ext = extension.lstrip(".").lower()
        folder = self._base / str(tenant_id) / str(batch_id)
        folder.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.{ext}"
        path = folder / filename
        path.write_bytes(content)

        relative = f"{tenant_id}/{batch_id}/{filename}"
        log.debug("Guardado fichero %s (%d bytes)", relative, len(content))
        return relative

    def read(self, relative_path: str) -> bytes:
        """Lee el contenido de un fichero a partir de su ruta relativa."""
        return (self._base / relative_path).read_bytes()

    def absolute_path(self, relative_path: str) -> Path:
        """Resuelve una ruta relativa a su ruta absoluta en disco."""
        return self._base / relative_path

    def exists(self, relative_path: str) -> bool:
        """Comprueba si un fichero existe."""
        return (self._base / relative_path).is_file()

    def delete(self, relative_path: str) -> None:
        """Borra un fichero. Si no existe no hace nada."""
        (self._base / relative_path).unlink(missing_ok=True)


_storage: FilesystemStorage | None = None


def get_storage() -> FilesystemStorage:
    """Obtiene el singleton de storage a partir de la configuración."""
    global _storage
    if _storage is None:
        settings = get_web_settings()
        _storage = FilesystemStorage(settings.storage.base_path)
    return _storage


def reset_storage() -> None:
    """Limpia el singleton (usado por tests)."""
    global _storage
    _storage = None


StorageDep = Annotated[FilesystemStorage, Depends(get_storage)]
