"""Gestión segura de API keys y credenciales con Fernet.

Las credenciales se almacenan cifradas en ``secrets.enc``.
La clave de cifrado se almacena en ``.secrets.key`` con permisos 0600.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config.settings import get_settings

log = logging.getLogger(__name__)


class SecretsError(Exception):
    """Error al operar con el almacén de secrets."""


class SecretsManager:
    """Almacén cifrado de API keys y credenciales.

    Estructura interna: diccionario JSON plano {nombre: valor}.
    Cifrado con Fernet (AES-128-CBC + HMAC-SHA256).

    Args:
        secrets_file: Ruta al fichero cifrado.
        key_file: Ruta al fichero con la clave Fernet.
    """

    def __init__(
        self,
        secrets_file: Path | None = None,
        key_file: Path | None = None,
    ) -> None:
        settings = get_settings()
        self._secrets_file = secrets_file or settings.secrets_file
        self._key_file = key_file or settings.secrets_key_file
        self._fernet: Fernet | None = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get(self, name: str) -> str | None:
        """Obtiene un secret por nombre. None si no existe."""
        data = self._load()
        return data.get(name)

    def set(self, name: str, value: str) -> None:
        """Almacena o actualiza un secret."""
        data = self._load()
        data[name] = value
        self._save(data)

    def delete(self, name: str) -> None:
        """Elimina un secret. No falla si no existe."""
        data = self._load()
        data.pop(name, None)
        self._save(data)

    def list_names(self) -> list[str]:
        """Devuelve los nombres de todos los secrets almacenados."""
        return list(self._load().keys())

    def has(self, name: str) -> bool:
        """Comprueba si un secret existe."""
        return name in self._load()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _secure_chmod(path: Path) -> None:
        """Aplica permisos 0600 en plataformas que lo soportan."""
        if sys.platform != "win32":
            path.chmod(0o600)

    def _get_fernet(self) -> Fernet:
        """Obtiene o inicializa la instancia Fernet."""
        if self._fernet is not None:
            return self._fernet

        if self._key_file.exists():
            key = self._key_file.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            self._key_file.parent.mkdir(parents=True, exist_ok=True)
            self._key_file.write_bytes(key)
            self._secure_chmod(self._key_file)
            log.info("Clave de cifrado generada en %s", self._key_file)

        self._fernet = Fernet(key)
        return self._fernet

    def _load(self) -> dict[str, str]:
        """Descifra y carga el diccionario de secrets."""
        if not self._secrets_file.exists():
            return {}

        f = self._get_fernet()
        encrypted = self._secrets_file.read_bytes()

        try:
            decrypted = f.decrypt(encrypted)
        except InvalidToken as e:
            raise SecretsError(
                "No se pudo descifrar el almacén de secrets. "
                "¿La clave es correcta?"
            ) from e

        try:
            return json.loads(decrypted)
        except json.JSONDecodeError as e:
            raise SecretsError(
                f"Contenido descifrado no es JSON válido: {e}"
            ) from e

    def _save(self, data: dict[str, str]) -> None:
        """Cifra y guarda el diccionario de secrets."""
        f = self._get_fernet()
        raw = json.dumps(data, ensure_ascii=False).encode()
        encrypted = f.encrypt(raw)

        self._secrets_file.parent.mkdir(parents=True, exist_ok=True)
        self._secrets_file.write_bytes(encrypted)
        self._secure_chmod(self._secrets_file)
