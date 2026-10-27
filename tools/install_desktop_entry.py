"""Instala (o quita) la entrada de escritorio de DocScan para ejecutarlo desde el código.

En Wayland, GNOME y KDE no usan el icono que pone la aplicación: lo buscan en
el fichero ``.desktop`` cuyo nombre coincide con el app_id de la ventana
(``docscan``, ver ``DESKTOP_FILE_NAME`` en ``main.py``). El AppImage trae el
suyo; ejecutando desde el repositorio no hay ninguno y sale un icono
genérico. Este script escribe ``~/.local/share/applications/docscan.desktop``
apuntando al venv y al icono del repositorio.

Uso:
    .venv/bin/python tools/install_desktop_entry.py
    .venv/bin/python tools/install_desktop_entry.py --uninstall
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("install_desktop_entry")

ROOT = Path(__file__).resolve().parent.parent
DESKTOP_NAME = "docscan.desktop"


def applications_dir() -> Path:
    """Carpeta de entradas de escritorio del usuario (XDG)."""
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    return Path(data_home) / "applications"


def desktop_entry(root: Path = ROOT, python: Path | None = None) -> str:
    """Contenido del .desktop para ejecutar desde ``root``."""
    python = python or root / ".venv" / "bin" / "python"
    icon = root / "resources" / "icons" / "docscan.svg"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=DocScan Studio\n"
        "GenericName=Document Scanner\n"
        "Comment=Batch document capture, processing and indexing with AI support\n"
        f'Exec="{python}" "{root / "main.py"}"\n'
        f"Path={root}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Graphics;Scanning;\n"
        "StartupNotify=true\n"
        "StartupWMClass=docscan\n"
    )


def _refresh_cache(directory: Path) -> None:
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(directory)], check=False)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uninstall", action="store_true", help="Quitar la entrada")
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        log.error("Solo hace falta en Linux.")
        return 1

    directory = applications_dir()
    target = directory / DESKTOP_NAME
    if args.uninstall:
        if target.exists():
            target.unlink()
            _refresh_cache(directory)
            log.info("Quitada: %s", target)
        else:
            log.info("No había entrada en %s", target)
        return 0

    directory.mkdir(parents=True, exist_ok=True)
    target.write_text(desktop_entry(), encoding="utf-8")
    _refresh_cache(directory)
    log.info("Instalada: %s", target)
    log.info("Vuelve a abrir DocScan para que el escritorio coja el icono.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
