"""Configuración global de pytest para DocScan Studio (desktop).

Hermetiza la suite frente a interacción manual y hardware real:

1. **Diálogos Qt no bloqueantes**: parchea los modales de PySide6
   (``QMessageBox``, ``QDialog.exec``, ``QFileDialog``, ``QInputDialog``) para
   que nunca esperen un clic del usuario. Un test que dispare un modal sin
   mockearlo obtiene una respuesta por defecto en lugar de colgar la suite
   esperando que alguien pulse «Aceptar».

2. **SANE hermético**: inyecta un módulo ``sane`` falso en ``sys.modules``
   antes de recolectar los tests, de modo que ningún test toque el escáner USB
   real. Esto elimina el prompt de autenticación de administrador
   (polkit/libusb) y los ~30 s de enumeración de hardware que provocaba
   ``create_scanner()`` sin mockear.

3. **QSettings aislado**: redirige la configuración persistente de Qt a un
   directorio temporal. Sin esto la suite lee y **escribe** los ajustes reales
   del usuario (registro de Windows / ``~/.config`` en Linux): los tests
   quedaban a merced de lo que el usuario hubiera dejado guardado —p.ej.
   ``source/<app_id>/mode = scanner`` hacía fallar
   ``test_scan_source_radio_defaults_to_import``— y además pisaban su
   configuración al ejecutarse.

Los tests que necesitan un valor de retorno concreto de un diálogo o de SANE
siguen mockeándolo localmente; su parche se aplica encima del global y se
restaura al terminar.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
from unittest import mock

import pytest

# --------------------------------------------------------------------------- #
# 0. Web SaaS archivada: saltar sus tests si faltan las dependencias web.
# --------------------------------------------------------------------------- #
# El venv de desarrollo desktop no instala fastapi/bcrypt/arq (viven en
# requirements-web.txt). Sin este filtro, `pytest tests/` mezcla la suite
# desktop con errores de colección de la web archivada. Los tests web solo se
# recolectan cuando sus dependencias están presentes (p.ej. en el CI web).


def _missing(module: str) -> bool:
    """True si `module` no es importable en el entorno actual."""
    try:
        return importlib.util.find_spec(module) is None
    except ImportError, ValueError:
        return True


collect_ignore_glob: list[str] = []
if _missing("fastapi") or _missing("bcrypt"):
    collect_ignore_glob += ["test_web_*.py", "test_pipeline_runner_events.py"]
if _missing("arq"):
    collect_ignore_glob += ["test_arq_*.py"]


# --------------------------------------------------------------------------- #
# 1. SANE hermético — se instala a nivel de import, antes de recolectar tests.
# --------------------------------------------------------------------------- #


def _install_fake_sane() -> None:
    """Sustituye el módulo ``sane`` por un doble inofensivo.

    Se instala siempre (haya o no ``python-sane`` instalado) para que la suite
    se comporte igual en el equipo con escáner y en CI sin hardware, y para que
    ninguna ruta de código pueda abrir el bus USB y disparar la autenticación
    de administrador.
    """
    fake = types.ModuleType("sane")

    def _init() -> tuple[int, int, int, int]:
        return (1, 1, 0, 0)

    def _exit() -> None:
        return None

    def _get_devices(*_args, **_kwargs) -> list:
        return []

    def _open(source: str):
        dev = mock.MagicMock(name=f"SaneDevice({source})")
        dev.opt = {}
        return dev

    fake.init = _init
    fake.exit = _exit
    fake.get_devices = _get_devices
    fake.open = _open
    # Constantes de tipo/unidad que scanner_service consulta al mapear opciones.
    fake.TYPE_BOOL = 0
    fake.TYPE_INT = 1
    fake.TYPE_FIXED = 2
    fake.TYPE_STRING = 3
    fake.TYPE_BUTTON = 4
    fake.TYPE_GROUP = 5
    fake.UNIT_NONE = 0
    fake.UNIT_PIXEL = 1
    fake.UNIT_BIT = 2
    fake.UNIT_MM = 3
    fake.UNIT_DPI = 4
    fake.UNIT_PERCENT = 5
    fake.UNIT_MICROSECOND = 6

    sys.modules["sane"] = fake


_install_fake_sane()


# --------------------------------------------------------------------------- #
# 1bis. QSettings aislado — también antes de recolectar tests.
# --------------------------------------------------------------------------- #


def _isolate_qsettings() -> None:
    """Redirige ``QSettings`` a un directorio temporal desechable.

    ``QSettings("DocScanStudio", ...)`` usa el backend nativo (registro en
    Windows, ``~/.config`` en Linux), que es **la configuración real del
    usuario**: la suite dependía de lo que el usuario tuviera guardado y además
    se lo pisaba al ejecutarse.

    ``setDefaultFormat()`` no basta —PySide6 sigue construyendo en
    ``NativeFormat`` desde el constructor de dos argumentos—, así que se
    sustituye la clase por una subclase que fuerza ``IniFormat`` y
    ``UserScope`` sobre un directorio temporal. Como ``conftest`` se importa
    antes que los módulos de la app, el ``from PySide6.QtCore import
    QSettings`` de estos recoge ya la subclase.
    """
    try:
        from PySide6 import QtCore
    except ImportError:
        # Entorno sin PySide6 (p.ej. solo tests web): nada que aislar.
        return

    real = QtCore.QSettings
    ini = real.Format.IniFormat
    user = real.Scope.UserScope
    real.setPath(ini, user, tempfile.mkdtemp(prefix="docscan-tests-qsettings-"))

    class _IsolatedQSettings(real):
        """``QSettings`` que ignora el backend nativo y escribe en el temporal."""

        def __init__(self, *args, **kwargs):
            if len(args) == 2 and all(isinstance(a, str) for a in args):
                super().__init__(ini, user, args[0], args[1], **kwargs)
            else:
                super().__init__(*args, **kwargs)

    QtCore.QSettings = _IsolatedQSettings


_isolate_qsettings()


# --------------------------------------------------------------------------- #
# 2. Diálogos Qt no bloqueantes.
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _no_blocking_dialogs():
    """Impide que cualquier diálogo modal de Qt bloquee la suite.

    Devuelve respuestas por defecto (aceptar en avisos, cancelar en selección)
    a los modales que un test no haya mockeado explícitamente. Un test que sí
    los mockee sobrescribe este parche mientras dure.
    """
    try:
        from PySide6.QtWidgets import (
            QDialog,
            QFileDialog,
            QInputDialog,
            QMessageBox,
        )
    except ImportError:
        # Entorno sin PySide6 (p.ej. solo se corren los tests web): nada que
        # parchear.
        yield
        return

    ok = QMessageBox.StandardButton.Ok
    yes = QMessageBox.StandardButton.Yes
    rejected = QDialog.DialogCode.Rejected

    patches = [
        mock.patch.object(QMessageBox, "information", return_value=ok),
        mock.patch.object(QMessageBox, "warning", return_value=ok),
        mock.patch.object(QMessageBox, "critical", return_value=ok),
        mock.patch.object(QMessageBox, "about", return_value=None),
        mock.patch.object(QMessageBox, "aboutQt", return_value=None),
        mock.patch.object(QMessageBox, "question", return_value=yes),
        mock.patch.object(QMessageBox, "exec", return_value=ok),
        # Diálogos genéricos sin mock explícito: por defecto «cancelado».
        mock.patch.object(QDialog, "exec", return_value=rejected),
        mock.patch.object(QFileDialog, "getOpenFileName", return_value=("", "")),
        mock.patch.object(QFileDialog, "getOpenFileNames", return_value=([], "")),
        mock.patch.object(QFileDialog, "getSaveFileName", return_value=("", "")),
        mock.patch.object(QFileDialog, "getExistingDirectory", return_value=""),
        mock.patch.object(QInputDialog, "getText", return_value=("", False)),
        mock.patch.object(QInputDialog, "getInt", return_value=(0, False)),
        mock.patch.object(QInputDialog, "getDouble", return_value=(0.0, False)),
        mock.patch.object(QInputDialog, "getItem", return_value=("", False)),
    ]

    started = []
    try:
        for p in patches:
            p.start()
            started.append(p)
        yield
    finally:
        for p in started:
            p.stop()
