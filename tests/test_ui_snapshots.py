"""Tests de la herramienta de capturas (tools/ui_snapshots.py).

Se ejecuta como proceso aparte: aísla el entorno (XDG, QSettings) cambiando
variables y clases globales, algo que no debe ocurrir dentro de la suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "ui_snapshots.py"


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ROOT,
    )


def test_lista_las_capturas_de_la_documentacion():
    res = _run("--list")
    assert res.returncode == 0
    nombres = set(res.stdout.split())
    usados = {p.stem for p in (ROOT / "docs-web" / "assets" / "screenshots").glob("*.png")}
    assert usados <= nombres, f"capturas de docs-web sin generador: {usados - nombres}"


def test_genera_capturas_aisladas(tmp_path):
    res = _run("--only", "about_dialog", "new_app_dialog", "--out", str(tmp_path))
    assert res.returncode == 0, res.stdout + res.stderr
    for nombre in ("about_dialog", "new_app_dialog"):
        assert (tmp_path / f"{nombre}.png").stat().st_size > 1000


def test_nombre_desconocido_falla():
    res = _run("--only", "no_existe")
    assert res.returncode != 0
