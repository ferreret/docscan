"""Servicio de editor externo para scripts.

Lanza VS Code (u otro editor) con ``--wait`` para edición bloqueante.
Inyecta stubs de contexto al inicio del archivo temporal.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from pathlib import Path

from app.services.script_stubs import generate_stubs, strip_stubs
from config.settings import APP_DATA_DIR

log = logging.getLogger(__name__)

_SCRIPTS_TMP_DIR = APP_DATA_DIR / "scripts_tmp"


def detect_editor() -> str | None:
    """Detecta si VS Code está disponible en el PATH."""
    path = shutil.which("code")
    return path if path else None


def edit_script(
    code: str,
    context_type: str = "pipeline",
    event_name: str = "",
) -> str | None:
    """Abre el código en VS Code con --wait.

    Bloquea hasta que el usuario cierre la pestaña en VS Code.
    Pensado para ejecutarse en un QThread.

    Args:
        code: Código fuente actual.
        context_type: "pipeline" o "event".
        event_name: Nombre del evento (si context_type="event").

    Returns:
        Código modificado (sin stubs), o None si fue cancelado/error.
    """
    editor = detect_editor()
    if editor is None:
        log.warning("VS Code no detectado en PATH")
        return None

    _SCRIPTS_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = _SCRIPTS_TMP_DIR / f"{uuid.uuid4().hex}.py"

    try:
        stubs = generate_stubs(context_type, event_name)
        tmp_file.write_text(stubs + code, encoding="utf-8")

        result = subprocess.run(
            [editor, "--wait", str(tmp_file)],
            check=False,
        )

        if result.returncode != 0:
            log.warning("VS Code retornó código %d", result.returncode)
            return None

        content = tmp_file.read_text(encoding="utf-8")
        return strip_stubs(content)

    except Exception as e:
        log.error("Error editando con VS Code: %s", e)
        return None
    finally:
        try:
            tmp_file.unlink(missing_ok=True)
        except Exception:
            pass
