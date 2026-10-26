"""Tests de tools/install_desktop_entry.py y del app_id de Wayland."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "install_desktop_entry", ROOT / "tools" / "install_desktop_entry.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_entrada_apunta_al_repo_y_al_icono():
    tool = _load_tool()
    entry = tool.desktop_entry(Path("/repo"), Path("/repo/.venv/bin/python"))
    assert 'Exec="/repo/.venv/bin/python" "/repo/main.py"' in entry
    assert "Icon=/repo/resources/icons/docscan.svg" in entry
    assert "StartupWMClass=docscan" in entry


def test_el_icono_existe():
    assert (ROOT / "resources" / "icons" / "docscan.svg").exists()


def test_nombre_coincide_con_el_app_id_y_el_appimage():
    """main.py, el script y el .desktop del AppImage usan el mismo nombre."""
    tool = _load_tool()
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'DESKTOP_FILE_NAME = "docscan"' in main_src
    # Antes de crear la QApplication, o el portal rechaza el app_id
    assert main_src.index("setDesktopFileName(DESKTOP_FILE_NAME)") < main_src.index(
        "QApplication(sys.argv)"
    )
    assert tool.DESKTOP_NAME == "docscan.desktop"
    assert (ROOT / "build" / "appimage" / "docscan.desktop").exists()


def test_instala_y_desinstala_en_xdg_data_home(tmp_path, monkeypatch):
    tool = _load_tool()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["install_desktop_entry.py"])
    monkeypatch.setattr(tool.shutil, "which", lambda _name: None)
    assert tool.main() == 0
    target = tmp_path / "applications" / "docscan.desktop"
    assert target.exists()
    monkeypatch.setattr("sys.argv", ["install_desktop_entry.py", "--uninstall"])
    assert tool.main() == 0
    assert not target.exists()
