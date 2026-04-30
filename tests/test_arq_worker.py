"""Tests del worker ARQ: handlers, lifecycle hooks y configuración."""

from __future__ import annotations

import pytest


def test_worker_settings_exposes_required_attributes():
    """WorkerSettings tiene functions, hooks y configuración mínima.

    Los handlers se registran con el nombre que enrola el router
    (``run_pipeline_for_batch`` / ``run_transfer_for_batch``) vía
    ``arq.worker.func(name=...)``; ``recovery_job`` mantiene su nombre
    porque es el que enrola el lifespan del API.
    """
    from arq.worker import Function

    from web.api.tasks.worker import WorkerSettings

    def _name(entry):
        return entry.name if isinstance(entry, Function) else entry.__name__

    func_names = {_name(f) for f in WorkerSettings.functions}
    assert "run_pipeline_for_batch" in func_names
    assert "run_transfer_for_batch" in func_names
    assert "recovery_job" in func_names

    assert hasattr(WorkerSettings, "on_startup")
    assert hasattr(WorkerSettings, "on_shutdown")
    assert WorkerSettings.max_tries == 1
    assert WorkerSettings.job_timeout == 600


@pytest.mark.asyncio
async def test_pipeline_job_calls_run_pipeline_for_batch_with_storage_from_ctx(
    monkeypatch,
):
    """El handler pipeline_job lee storage del ctx y llama al runner."""
    from web.api.tasks import worker as worker_mod

    called = {"args": None, "kwargs": None}

    def fake_runner(batch_id, storage):
        called["args"] = (batch_id,)
        called["kwargs"] = {"storage": storage}

    monkeypatch.setattr(worker_mod, "_pipeline_runner", fake_runner)

    sentinel_storage = object()
    ctx = {"storage": sentinel_storage}
    await worker_mod.pipeline_job(ctx, batch_id=42)

    assert called == {"args": (42,), "kwargs": {"storage": sentinel_storage}}


@pytest.mark.asyncio
async def test_transfer_job_calls_run_transfer_for_batch_with_storage_from_ctx(
    monkeypatch,
):
    """El handler transfer_job lee storage del ctx y llama al runner."""
    from web.api.tasks import worker as worker_mod

    called = {"kwargs": None}

    def fake_runner(batch_id, storage):
        called["kwargs"] = {"batch_id": batch_id, "storage": storage}

    monkeypatch.setattr(worker_mod, "_transfer_runner", fake_runner)

    sentinel_storage = object()
    ctx = {"storage": sentinel_storage}
    await worker_mod.transfer_job(ctx, batch_id=99)

    assert called == {"kwargs": {"batch_id": 99, "storage": sentinel_storage}}
