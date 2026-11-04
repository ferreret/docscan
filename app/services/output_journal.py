"""Registro de la salida de una transferencia, para poder retirarla.

Paridad con FlexibarNET10 v1.27: si una transferencia falla a medias, no debe
quedar salida parcial en el destino. Sin esto, el reintento creaba duplicados
``_1`` y, con la colisión «Fusionar», volvía a anexar al PDF/TIFF las páginas
que ya se habían añadido en el intento fallido.

El registro anota, **antes** de cada escritura, qué ficheros y carpetas crea
la transferencia y guarda una copia de los que ya existían y va a modificar
(sobrescribir o ampliar). ``rollback`` deja el destino como estaba;
``commit`` acepta la salida y borra las copias.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

#: Marca de las copias de seguridad que se dejan junto al fichero original.
BACKUP_MARK = ".docscan-bak"


class OutputJournal:
    """Anota la salida de una transferencia para confirmarla o retirarla."""

    def __init__(self) -> None:
        self._token = uuid.uuid4().hex[:8]
        # Ficheros creados por esta transferencia (no existían antes).
        self._created: list[Path] = []
        # Ficheros que ya existían → copia de su contenido original.
        self._backups: dict[Path, Path] = {}
        # Carpetas creadas, en orden de creación.
        self._dirs: list[Path] = []
        self._closed = False

    @property
    def is_empty(self) -> bool:
        """True si la transferencia no ha escrito nada."""
        return not (self._created or self._backups or self._dirs)

    def mkdir(self, path: Path) -> None:
        """Crea ``path`` (y sus padres) anotando las carpetas nuevas."""
        missing: list[Path] = []
        current = Path(path)
        while not current.exists():
            missing.append(current)
            if current.parent == current:
                break
            current = current.parent
        path.mkdir(parents=True, exist_ok=True)
        self._dirs.extend(reversed(missing))

    def prepare(self, path: Path) -> None:
        """Llamar antes de escribir ``path`` (crearlo, sobrescribirlo o ampliarlo).

        Si ya existía y no lo ha creado esta transferencia, guarda una copia
        para poder restaurarlo.
        """
        path = Path(path)
        if path in self._backups or path in self._created:
            return
        if path.exists():
            backup = path.with_name(f".{path.name}.{self._token}{BACKUP_MARK}")
            shutil.copy2(path, backup)
            self._backups[path] = backup
        else:
            self._created.append(path)

    def commit(self) -> None:
        """Acepta la salida: borra las copias de seguridad."""
        if self._closed:
            return
        for backup in self._backups.values():
            backup.unlink(missing_ok=True)
        self._closed = True

    def rollback(self) -> list[str]:
        """Retira la salida: borra lo creado y restaura lo modificado.

        Returns:
            Problemas encontrados al retirar (vacío si todo fue bien). No se
            lanza: quien llama ya está informando de un fallo.
        """
        if self._closed:
            return []
        self._closed = True
        problems: list[str] = []
        for path in reversed(self._created):
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                problems.append(f"No se pudo retirar '{path}': {e}")
        for path, backup in self._backups.items():
            try:
                backup.replace(path)
            except OSError as e:
                problems.append(f"No se pudo restaurar '{path}': {e}")
        for directory in reversed(self._dirs):
            try:
                directory.rmdir()  # solo si ha quedado vacía
            except OSError:
                pass
        if problems:
            for problem in problems:
                log.error(problem)
        else:
            log.info(
                "Salida retirada: %d fichero(s) borrados, %d restaurados",
                len(self._created),
                len(self._backups),
            )
        return problems
