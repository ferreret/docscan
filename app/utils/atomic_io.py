"""Escritura atómica de ficheros: temporal + rename.

Escribir directamente sobre el fichero definitivo deja una ventana en la
que el contenido está truncado. Si la aplicación se cierra (o el sistema
se apaga) justo en ese instante, el fichero queda corrupto y en el
siguiente arranque no se puede leer: preferencias perdidas, almacén de
credenciales ilegible, pack de aplicación a medias.

El patrón de estas funciones evita esa ventana: se escribe un temporal en
el **mismo directorio** (para que el rename no cruce sistemas de
ficheros), se fuerza su volcado a disco y solo entonces se sustituye al
definitivo con ``os.replace()``, que es atómico en POSIX y en Windows.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
    *,
    chmod: int | None = None,
) -> None:
    """Escribe bytes de forma atómica.

    Args:
        path: Ruta del fichero destino. Su directorio se crea si falta.
        data: Contenido a escribir.
        chmod: Permisos a aplicar al fichero antes del rename (p. ej.
            ``0o600``). None deja los permisos por defecto.

    Raises:
        OSError: Si falla la escritura o el reemplazo. El fichero
            original queda intacto.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if chmod is not None:
            os.chmod(tmp_path, chmod)

        os.replace(tmp_path, path)
    except BaseException:
        # No dejar temporales huérfanos si algo falla a mitad.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            log.warning("No se pudo borrar el temporal %s", tmp_path)
        raise

    _fsync_dir(path.parent)


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    chmod: int | None = None,
) -> None:
    """Escribe texto de forma atómica.

    Args:
        path: Ruta del fichero destino.
        text: Contenido a escribir.
        encoding: Codificación (por defecto UTF-8).
        chmod: Permisos a aplicar antes del rename.

    Raises:
        OSError: Si falla la escritura o el reemplazo.
    """
    atomic_write_bytes(path, text.encode(encoding), chmod=chmod)


def _fsync_dir(directory: Path) -> None:
    """Fuerza el volcado de la entrada de directorio tras el rename.

    Sin esto, en POSIX el rename puede no haber llegado a disco aunque el
    contenido sí. Es best-effort: en Windows no aplica y en algunos
    sistemas de ficheros no está permitido, así que los fallos solo se
    registran.
    """
    if os.name != "posix":
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError as e:
        log.debug("No se pudo abrir %s para fsync: %s", directory, e)
        return
    try:
        os.fsync(fd)
    except OSError as e:
        log.debug("fsync de directorio %s no soportado: %s", directory, e)
    finally:
        os.close(fd)
