"""Servicio de auto-actualización via GitHub Releases.

Comprueba si hay nuevas versiones disponibles, descarga el instalador
apropiado para la plataforma y verifica su integridad con SHA-256.
"""

from __future__ import annotations

import hashlib
import logging
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
from packaging.version import Version, InvalidVersion

from app._version import __version__

log = logging.getLogger(__name__)

_GITHUB_OWNER = "ferreret"
_GITHUB_REPO = "docscan"
_API_BASE = f"https://api.github.com/repos/{_GITHUB_OWNER}/{_GITHUB_REPO}"
_TIMEOUT = 10


@dataclass
class ReleaseInfo:
    """Información de una release disponible en GitHub."""

    version: str
    tag_name: str
    published_at: str
    release_notes: str
    html_url: str
    asset_url: str
    asset_name: str
    asset_size: int
    sha256: str


@dataclass
class UpdateCheckResult:
    """Resultado de la comprobación de actualizaciones."""

    available: bool
    current_version: str
    latest: ReleaseInfo | None = None
    error: str | None = None


class UpdateService:
    """Gestiona la comprobación y descarga de actualizaciones.

    Lógica pura sin dependencias de Qt — testable de forma independiente.
    """

    def __init__(
        self,
        owner: str = _GITHUB_OWNER,
        repo: str = _GITHUB_REPO,
    ) -> None:
        self._api_base = f"https://api.github.com/repos/{owner}/{repo}"
        self._current = Version(__version__)

    @property
    def current_version(self) -> str:
        return str(self._current)

    # ------------------------------------------------------------------
    # Comprobación de actualizaciones
    # ------------------------------------------------------------------

    def check_for_update(self) -> UpdateCheckResult:
        """Consulta GitHub Releases y compara con la versión actual.

        Returns:
            UpdateCheckResult con la información de la release si hay
            una versión más nueva disponible.
        """
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(f"{self._api_base}/releases/latest")

                if resp.status_code == 404:
                    return UpdateCheckResult(
                        available=False,
                        current_version=self.current_version,
                    )

                resp.raise_for_status()
                release = resp.json()

                if release.get("prerelease") or release.get("draft"):
                    return UpdateCheckResult(
                        available=False,
                        current_version=self.current_version,
                    )

                tag = release["tag_name"].lstrip("v")
                try:
                    latest_version = Version(tag)
                except InvalidVersion:
                    return UpdateCheckResult(
                        available=False,
                        current_version=self.current_version,
                        error=f"Versión inválida en release: {tag}",
                    )

                if latest_version <= self._current:
                    return UpdateCheckResult(
                        available=False,
                        current_version=self.current_version,
                    )

                # Buscar asset para esta plataforma
                asset = self._find_platform_asset(release.get("assets", []))
                if asset is None:
                    return UpdateCheckResult(
                        available=True,
                        current_version=self.current_version,
                        error="No hay instalador disponible para tu plataforma",
                    )

                # Buscar SHA256
                sha256 = self._fetch_sha256(
                    release.get("assets", []), asset["name"], client,
                )

                info = ReleaseInfo(
                    version=str(latest_version),
                    tag_name=release["tag_name"],
                    published_at=release.get("published_at", ""),
                    release_notes=release.get("body", ""),
                    html_url=release.get("html_url", ""),
                    asset_url=asset["browser_download_url"],
                    asset_name=asset["name"],
                    asset_size=asset.get("size", 0),
                    sha256=sha256,
                )

                return UpdateCheckResult(
                    available=True,
                    current_version=self.current_version,
                    latest=info,
                )

        except httpx.TimeoutException:
            log.debug("Timeout al comprobar actualizaciones")
            return UpdateCheckResult(
                available=False,
                current_version=self.current_version,
                error="Timeout al conectar con GitHub",
            )
        except Exception as e:
            log.warning("Error al comprobar actualizaciones: %s", e)
            return UpdateCheckResult(
                available=False,
                current_version=self.current_version,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------

    def download_update(
        self,
        release: ReleaseInfo,
        dest_dir: Path,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Descarga el instalador de la release.

        Args:
            release: Información de la release a descargar.
            dest_dir: Directorio donde guardar el fichero.
            on_progress: Callback (bytes_descargados, bytes_totales).

        Returns:
            Ruta del fichero descargado.

        Raises:
            httpx.HTTPError: Si la descarga falla.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / release.asset_name

        with httpx.Client(timeout=None, follow_redirects=True) as client:
            with client.stream("GET", release.asset_url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, total)

        log.info("Descarga completada: %s (%d bytes)", dest_path.name, downloaded)
        return dest_path

    # ------------------------------------------------------------------
    # Verificación
    # ------------------------------------------------------------------

    @staticmethod
    def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
        """Verifica la integridad del fichero con SHA-256.

        Args:
            file_path: Ruta del fichero descargado.
            expected_sha256: Hash esperado en hexadecimal.

        Returns:
            True si el checksum coincide.
        """
        if not expected_sha256:
            log.warning("No hay checksum disponible, se omite la verificación")
            return True

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)

        actual = sha256.hexdigest()
        if actual.lower() != expected_sha256.lower():
            log.error(
                "Checksum inválido: esperado=%s, actual=%s",
                expected_sha256[:16], actual[:16],
            )
            return False

        log.info("Checksum verificado correctamente")
        return True

    # ------------------------------------------------------------------
    # Aplicación de la actualización
    # ------------------------------------------------------------------

    @staticmethod
    def apply_update(installer_path: Path) -> None:
        """Aplica la actualización según la plataforma.

        - Linux (AppImage): reemplaza el fichero y notifica reinicio.
        - Windows (Inno Setup): lanza el installer en modo silencioso.

        Args:
            installer_path: Ruta del instalador descargado.
        """
        import subprocess
        import sys

        system = platform.system()

        if system == "Linux":
            # Reemplazar AppImage si estamos ejecutando desde uno
            current_appimage = Path(sys.argv[0]).resolve()
            if current_appimage.suffix == ".AppImage":
                installer_path.chmod(0o755)
                installer_path.rename(current_appimage)
                log.info("AppImage reemplazado. Reinicie la aplicación.")
            else:
                log.info(
                    "Instalador descargado en: %s. "
                    "Ejecute manualmente para actualizar.",
                    installer_path,
                )

        elif system == "Windows":
            # Lanzar Inno Setup en modo silencioso
            subprocess.Popen(
                [str(installer_path), "/SILENT", "/CLOSEAPPLICATIONS"],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            log.info("Installer lanzado. La aplicación se cerrará.")
            sys.exit(0)

        else:
            log.warning("Plataforma no soportada para auto-update: %s", system)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_platform_asset(assets: list[dict[str, Any]]) -> dict | None:
        """Selecciona el asset apropiado para la plataforma actual."""
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Mapear a convenciones de nombre de asset
        if system == "linux":
            patterns = [".appimage"]
        elif system == "windows":
            patterns = ["-setup.exe", "-installer.exe", ".exe"]
        else:
            return None

        arch = "x86_64" if machine in ("x86_64", "amd64") else machine

        for asset in assets:
            name = asset["name"].lower()
            if any(name.endswith(p) for p in patterns):
                if arch in name or "x64" in name or system in name:
                    return asset

        # Fallback: buscar solo por extensión
        for asset in assets:
            name = asset["name"].lower()
            if any(name.endswith(p) for p in patterns):
                return asset

        return None

    @staticmethod
    def _fetch_sha256(
        assets: list[dict[str, Any]],
        target_name: str,
        client: httpx.Client,
    ) -> str:
        """Busca el SHA-256 del asset en SHA256SUMS.txt de la release."""
        sums_asset = next(
            (a for a in assets if a["name"].upper() == "SHA256SUMS.TXT"),
            None,
        )
        if sums_asset is None:
            return ""

        try:
            resp = client.get(
                sums_asset["browser_download_url"],
                follow_redirects=True,
            )
            resp.raise_for_status()
            for line in resp.text.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].lstrip("*") == target_name:
                    return parts[0]
        except Exception as e:
            log.debug("No se pudo obtener SHA256SUMS.txt: %s", e)

        return ""
