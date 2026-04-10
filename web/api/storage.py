"""Storage de ficheros de páginas (imágenes y PDFs).

Dos backends disponibles:
- ``FilesystemStorage``: disco local (desarrollo / on-premise).
- ``MinIOStorage``: S3-compatible via MinIO (producción / Docker).

Layout de objetos: ``{tenant_id}/{batch_id}/{uuid}.{ext}``
"""

from __future__ import annotations

import io
import logging
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from web.api.config import get_web_settings

log = logging.getLogger(__name__)


class BaseStorage(ABC):
    """Interfaz abstracta de storage de ficheros."""

    @abstractmethod
    def save(
        self,
        tenant_id: int,
        batch_id: int,
        content: bytes,
        extension: str,
    ) -> str:
        """Guarda bytes y devuelve la clave relativa."""

    @abstractmethod
    def read(self, relative_path: str) -> bytes:
        """Lee el contenido completo de un fichero."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Comprueba si un fichero existe."""

    @abstractmethod
    def delete(self, relative_path: str) -> None:
        """Borra un fichero. Si no existe no hace nada."""


def _object_key(tenant_id: int, batch_id: int, extension: str) -> str:
    """Genera la clave relativa ``{tenant}/{batch}/{uuid}.{ext}``."""
    ext = extension.lstrip(".").lower()
    return f"{tenant_id}/{batch_id}/{uuid.uuid4().hex}.{ext}"


class FilesystemStorage(BaseStorage):
    """Almacén de ficheros en disco local."""

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
        key = _object_key(tenant_id, batch_id, extension)
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        log.debug("Guardado fichero %s (%d bytes)", key, len(content))
        return key

    def read(self, relative_path: str) -> bytes:
        return (self._base / relative_path).read_bytes()

    def exists(self, relative_path: str) -> bool:
        return (self._base / relative_path).is_file()

    def delete(self, relative_path: str) -> None:
        (self._base / relative_path).unlink(missing_ok=True)

    # Método legacy — solo disponible en filesystem, NO en la ABC.
    def absolute_path(self, relative_path: str) -> Path:
        """Resuelve una ruta relativa a su ruta absoluta en disco."""
        return self._base / relative_path


class MinIOStorage(BaseStorage):
    """Almacén de ficheros en MinIO (S3-compatible)."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        use_ssl: bool = False,
    ) -> None:
        from minio import Minio

        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=use_ssl,
        )
        self._bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Crea el bucket si no existe."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            log.info("Bucket '%s' creado en MinIO", self._bucket)

    def save(
        self,
        tenant_id: int,
        batch_id: int,
        content: bytes,
        extension: str,
    ) -> str:
        key = _object_key(tenant_id, batch_id, extension)
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=io.BytesIO(content),
            length=len(content),
        )
        log.debug("MinIO: guardado %s (%d bytes)", key, len(content))
        return key

    def read(self, relative_path: str) -> bytes:
        response = None
        try:
            response = self._client.get_object(
                bucket_name=self._bucket,
                object_name=relative_path,
            )
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    def exists(self, relative_path: str) -> bool:
        from minio.error import S3Error

        try:
            self._client.stat_object(self._bucket, relative_path)
            return True
        except S3Error:
            return False

    def delete(self, relative_path: str) -> None:
        from minio.error import S3Error

        try:
            self._client.remove_object(self._bucket, relative_path)
        except S3Error:
            pass


# ------------------------------------------------------------------
# Singleton + Dependency Injection
# ------------------------------------------------------------------

_storage: BaseStorage | None = None


def get_storage() -> BaseStorage:
    """Obtiene el singleton de storage según la configuración."""
    global _storage
    if _storage is None:
        settings = get_web_settings()
        if settings.storage.backend == "minio":
            _storage = MinIOStorage(
                endpoint=settings.minio.endpoint,
                access_key=settings.minio.access_key,
                secret_key=settings.minio.secret_key,
                bucket=settings.minio.bucket,
                use_ssl=settings.minio.use_ssl,
            )
            log.info("Storage backend: MinIO (%s)", settings.minio.endpoint)
        else:
            _storage = FilesystemStorage(settings.storage.base_path)
            log.info("Storage backend: filesystem (%s)", settings.storage.base_path)
    return _storage


def reset_storage() -> None:
    """Limpia el singleton (usado por tests)."""
    global _storage
    _storage = None


StorageDep = Annotated[BaseStorage, Depends(get_storage)]
