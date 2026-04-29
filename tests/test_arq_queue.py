"""Tests del módulo web/api/tasks/queue.py y la configuración asociada."""

from __future__ import annotations




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
