"""Router del editor de pipeline de una aplicación.

Expone dos endpoints:

- ``GET /applications/{app_id}/pipeline`` — lee el pipeline actual.
- ``PUT /applications/{app_id}/pipeline`` — reemplaza el pipeline entero.

La validación se delega a ``app.pipeline.serializer.deserialize()``,
que es la misma función que usa el runner del pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.pipeline.serializer import (
    PipelineSerializationError,
    deserialize,
    serialize,
)
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.schemas.pipeline import PipelineResponse, PipelineUpdate

router = APIRouter()


def _get_app_or_404(app_id: int, tenant_id: int, db: Session) -> Application:
    """Obtiene una aplicación del tenant actual o lanza 404.

    Duplicado controlado: existe helper equivalente en applications.py,
    pero duplicarlo aquí evita un import cruzado entre routers.
    """
    app = db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicación no encontrada",
        )
    return app


def _steps_as_dicts(json_str: str) -> list[dict]:
    """Convierte el pipeline_json a lista de dicts (via deserialize + asdict).

    Pasa por deserialize para validar y filtrar tipos eliminados
    (REMOVED_STEP_TYPES), y luego re-serializa a dicts para el cliente.
    """
    from dataclasses import asdict

    steps = deserialize(json_str) if json_str else []
    return [asdict(s) for s in steps]


@router.get("/{app_id}/pipeline", response_model=PipelineResponse)
def get_pipeline(app_id: int, user: CurrentUser, db: SessionDep):
    """Devuelve el pipeline de la aplicación."""
    app = _get_app_or_404(app_id, user.tenant_id, db)
    try:
        steps = _steps_as_dicts(app.pipeline_json or "[]")
    except PipelineSerializationError as e:
        # Pipeline corrupto en BD: devolver vacío y loggear
        import logging

        logging.getLogger(__name__).warning(
            "Pipeline corrupto en app %d: %s", app_id, e
        )
        steps = []
    return {"steps": steps}


@router.put("/{app_id}/pipeline", response_model=PipelineResponse)
def update_pipeline(
    app_id: int,
    data: PipelineUpdate,
    user: CurrentUser,
    db: SessionDep,
):
    """Reemplaza el pipeline entero de la aplicación.

    Valida con ``deserialize()`` para garantizar que el pipeline
    guardado es ejecutable por el runner. Si falla, responde 422.
    """
    app = _get_app_or_404(app_id, user.tenant_id, db)

    # Construir JSON del cliente y validar vía deserialize
    import json

    raw_steps = [step.model_dump() for step in data.steps]
    candidate_json = json.dumps(raw_steps, ensure_ascii=False)

    try:
        steps = deserialize(candidate_json)
    except PipelineSerializationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipeline inválido: {e}",
        )

    # Re-serializar con la versión canónica (tuplas→listas, etc.)
    app.pipeline_json = serialize(steps)
    db.commit()

    from dataclasses import asdict

    return {"steps": [asdict(s) for s in steps]}
