"""Tests de la recuperación de lotes huérfanos al arrancar el worker."""

from __future__ import annotations

# Reutiliza fixtures del test_web_api para tener una BD lista.
from tests.test_web_api import (  # noqa: F401  — fixtures
    _auth_header,
    _create_app_with_pipeline,
    _create_batch_with_page,
    _test_engine,
    client,
    db_session,
    storage_dir,
)


def test_recovery_marks_running_batches_as_error_read(client, db_session):  # noqa: F811
    """Lotes en estado 'running' al arrancar el worker se marcan error_read."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    # Forzar el estado 'running' como si el worker hubiera muerto a media.
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    batch.state = "running"
    db_session.commit()

    n = recover_stuck_batches()
    assert n == 1

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "error_read"


def test_recovery_marks_transferring_batches_as_error_read(client, db_session):  # noqa: F811
    """Lotes en 'transferring' se recuperan a error_read."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    batch.state = "transferring"
    db_session.commit()

    n = recover_stuck_batches()
    assert n == 1

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "error_read"


def test_recovery_no_op_when_no_stuck_batches(client, db_session):  # noqa: F811
    """Si no hay batches huérfanos, devuelve 0 y no toca nada."""
    from app.models.batch import Batch
    from web.api.tasks.recovery import recover_stuck_batches

    headers = _auth_header(client)
    app_id = _create_app_with_pipeline(client, headers, "[]")
    batch_id, _ = _create_batch_with_page(client, headers, app_id)

    # Estado normal: 'created'
    n = recover_stuck_batches()
    assert n == 0

    db_session.expire_all()
    batch = db_session.query(Batch).filter_by(id=batch_id).first()
    assert batch.state == "created"
