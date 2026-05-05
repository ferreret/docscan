"""Tests del lifespan del API en modo ARQ (no-inline)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_lifespan_opens_pool_and_enrols_recovery_when_not_inline(monkeypatch):
    """Cuando inline=False, el lifespan llama a get_arq_pool y enrola recovery."""
    from web.api import main as main_mod

    # Settings con inline=False
    settings = MagicMock()
    settings.tasks.inline = False
    settings.deploy_mode = "cloud"
    settings.debug = False
    monkeypatch.setattr(main_mod, "get_web_settings", lambda: settings)

    # Mockear los hooks de ARQ.
    pool_mock = AsyncMock()
    enqueue_mock = AsyncMock()
    close_mock = AsyncMock()
    monkeypatch.setattr(main_mod, "get_arq_pool", pool_mock)
    monkeypatch.setattr(main_mod, "enqueue_or_run", enqueue_mock)
    monkeypatch.setattr(main_mod, "close_arq_pool", close_mock)

    # Stubs para BD y event bus.
    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value.execute.return_value = None
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine_mock)
    monkeypatch.setattr(main_mod, "reset_engine", lambda: None)
    bus_mock = MagicMock()
    monkeypatch.setattr(main_mod, "get_event_bus", lambda: bus_mock)

    # Ejercer el context manager.
    app_mock = MagicMock()
    async with main_mod.lifespan(app_mock):
        pass

    pool_mock.assert_awaited_once()
    enqueue_mock.assert_awaited_once_with("recovery_job")
    close_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_skips_arq_setup_when_inline(monkeypatch):
    """Cuando inline=True (tests), no toca ARQ."""
    from web.api import main as main_mod

    settings = MagicMock()
    settings.tasks.inline = True
    settings.deploy_mode = "onpremise"
    settings.debug = False
    monkeypatch.setattr(main_mod, "get_web_settings", lambda: settings)

    pool_mock = AsyncMock()
    enqueue_mock = AsyncMock()
    close_mock = AsyncMock()
    monkeypatch.setattr(main_mod, "get_arq_pool", pool_mock)
    monkeypatch.setattr(main_mod, "enqueue_or_run", enqueue_mock)
    monkeypatch.setattr(main_mod, "close_arq_pool", close_mock)

    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value.execute.return_value = None
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine_mock)
    monkeypatch.setattr(main_mod, "reset_engine", lambda: None)
    bus_mock = MagicMock()
    monkeypatch.setattr(main_mod, "get_event_bus", lambda: bus_mock)

    app_mock = MagicMock()
    async with main_mod.lifespan(app_mock):
        pass

    pool_mock.assert_not_awaited()
    enqueue_mock.assert_not_awaited()
    close_mock.assert_not_awaited()
