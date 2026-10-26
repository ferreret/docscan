"""Tests de la red global de excepciones y la traza de arranque."""

from __future__ import annotations

import logging
import sys
import threading

from app._version import __version__
from app.utils import crash_logging


def test_excepcion_no_capturada_va_al_log_con_traza(caplog, monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    crash_logging.install_exception_hooks()
    try:
        raise ValueError("boom")
    except ValueError:
        with caplog.at_level(logging.CRITICAL, logger="docscan.crash"):
            sys.excepthook(*sys.exc_info())
    registro = caplog.records[-1]
    assert registro.levelno == logging.CRITICAL
    assert registro.exc_info and registro.exc_info[0] is ValueError


def test_excepcion_en_hilo_va_al_log(caplog, monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    crash_logging.install_exception_hooks()

    def falla():
        raise RuntimeError("en hilo")

    with caplog.at_level(logging.CRITICAL, logger="docscan.crash"):
        t = threading.Thread(target=falla, name="hilo-prueba")
        t.start()
        t.join()
    assert any("hilo-prueba" in r.getMessage() for r in caplog.records)


def test_arranque_registra_version(caplog):
    with caplog.at_level(logging.INFO, logger="docscan"):
        crash_logging.log_startup("DocScan Studio")
    assert any(__version__ in r.getMessage() for r in caplog.records)
