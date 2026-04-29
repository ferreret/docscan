"""Tests del módulo web/api/tasks/queue.py y la configuración asociada."""

from __future__ import annotations

import pytest


def test_tasks_settings_default_inline_true_in_tests(monkeypatch):
    """Por defecto en pytest la cola corre en modo inline (sin Redis)."""
    # Forzar recarga del módulo de settings con el entorno limpio.
    monkeypatch.delenv("DOCSCAN_WEB_TASKS__INLINE", raising=False)

    from web.api.config import WebSettings

    settings = WebSettings()
    assert settings.tasks.inline is True
    assert settings.tasks.queue_name == "arq:queue"


def test_tasks_settings_can_disable_inline_via_env(monkeypatch):
    """En producción se desactiva inline poniendo la env var."""
    monkeypatch.setenv("DOCSCAN_WEB_TASKS__INLINE", "false")

    from web.api.config import WebSettings

    settings = WebSettings()
    assert settings.tasks.inline is False


@pytest.mark.asyncio
async def test_enqueue_or_run_inline_calls_function_directly(monkeypatch):
    """En modo inline ejecuta la función registrada en el mismo proceso."""
    from web.api.tasks import queue as queue_mod

    called = {"args": None, "kwargs": None}

    def my_runner(value: int, label: str = "x") -> None:
        called["args"] = (value,)
        called["kwargs"] = {"label": label}

    queue_mod.register_inline_runner("my_runner", my_runner)

    settings = type("S", (), {"tasks": type("T", (), {"inline": True})()})()
    monkeypatch.setattr(queue_mod, "_settings_for_test", settings)

    await queue_mod.enqueue_or_run("my_runner", 42, label="hola")

    assert called == {"args": (42,), "kwargs": {"label": "hola"}}


@pytest.mark.asyncio
async def test_enqueue_or_run_inline_raises_for_unknown_function(monkeypatch):
    """Si la función no está registrada, lanza KeyError explícito."""
    from web.api.tasks import queue as queue_mod

    settings = type("S", (), {"tasks": type("T", (), {"inline": True})()})()
    monkeypatch.setattr(queue_mod, "_settings_for_test", settings)

    with pytest.raises(KeyError, match="no_existe"):
        await queue_mod.enqueue_or_run("no_existe")


def test_pipeline_and_transfer_runners_are_registered_inline():
    """Los runners se auto-registran al importar sus módulos."""
    from web.api.tasks import queue as queue_mod
    import web.api.tasks.pipeline_runner  # noqa: F401 — fuerza el import
    import web.api.tasks.transfer_runner  # noqa: F401

    assert "run_pipeline_for_batch" in queue_mod._INLINE_REGISTRY
    assert "run_transfer_for_batch" in queue_mod._INLINE_REGISTRY
