"""Endpoint POST /transfer-batch — descarga el lote del SaaS al disco local.

Hito 11 sprint cliente local web. Caso de uso "servidor remoto sin
acceso a la red del cliente": el SaaS está en cloud y el operario
necesita las páginas finales (post-pipeline) en un disco/red local
del PC. El agente descarga el ZIP del lote (endpoint
``/api/batches/{id}/export`` del SaaS, que el hito 11 amplió para
aceptar agent_token) y lo escribe en una ruta del operario.

Modos:
- ``extracted`` (default): el ZIP se extrae en
  ``{destination}/batch_{id}/`` (páginas + manifest.json sueltos).
- ``zip``: el ZIP se escribe tal cual en
  ``{destination}/batch_{id}.zip``.

Errores:
- 401 sin pairing.
- 400 destination apunta a un fichero (no directorio).
- 404 lote ajeno (relayed del SaaS).
- 500 ZIP corrupto o error de I/O al escribir.
- 502 SaaS inalcanzable.

Decisión: sin streaming. Una sola request síncrona — el frontend
muestra spinner. Si más adelante el lote es enorme y queremos progreso
fino, conviértelo a NDJSON como el ADF (hito 8).
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from docscan_local_agent.credentials import AgentCredentials
from docscan_local_agent.deps import (
    SaasClientFactory,
    get_saas_client_factory,
    require_paired,
)
from docscan_local_agent.saas_client import ExportError, SaasUnavailable

log = logging.getLogger(__name__)

router = APIRouter(tags=["transfer"])

TransferMode = Literal["extracted", "zip"]


class TransferBatchRequest(BaseModel):
    """Body del POST /transfer-batch."""

    batch_id: int = Field(..., gt=0)
    destination: str = Field(
        ...,
        min_length=1,
        description="Ruta absoluta donde escribir. Se crea si no existe.",
    )
    mode: TransferMode = Field(
        default="extracted",
        description="'extracted' extrae el ZIP en una carpeta; 'zip' lo guarda sin abrir.",
    )


class TransferBatchResponse(BaseModel):
    """Respuesta de POST /transfer-batch."""

    batch_id: int
    mode: TransferMode
    path: str
    files_count: int
    bytes: int


@router.post("/transfer-batch", response_model=TransferBatchResponse)
def transfer_batch(
    body: TransferBatchRequest,
    creds: AgentCredentials = Depends(require_paired),
    saas_factory: SaasClientFactory = Depends(get_saas_client_factory),
) -> TransferBatchResponse:
    """Descarga el ZIP del lote y lo escribe en disco local."""
    destination = Path(body.destination)

    # Validación previa: si destination existe y es un fichero, abortar.
    # La intención es ofrecer una carpeta destino, no sobreescribir un
    # fichero suelto del operario por error de tipeo.
    if destination.exists() and not destination.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La ruta destino apunta a un fichero existente: {destination}",
        )

    # Crear el directorio si no existe (mkdir -p).
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.exception("No se pudo crear destination=%s", destination)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear el directorio destino: {exc}",
        ) from exc

    # Descargar el ZIP del SaaS.
    with saas_factory(creds.saas_url) as saas:
        try:
            zip_bytes = saas.download_batch_export(
                batch_id=body.batch_id,
                agent_token=creds.agent_token,
            )
        except ExportError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except SaasUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SaaS inalcanzable: {exc}",
            ) from exc

    # Escribir según el modo.
    if body.mode == "zip":
        return _write_zip_as_is(body.batch_id, destination, zip_bytes)
    return _extract_zip(body.batch_id, destination, zip_bytes)


def _write_zip_as_is(
    batch_id: int,
    destination: Path,
    zip_bytes: bytes,
) -> TransferBatchResponse:
    target = destination / f"batch_{batch_id}.zip"
    try:
        target.write_bytes(zip_bytes)
    except OSError as exc:
        log.exception("Error escribiendo ZIP a %s", target)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error escribiendo el ZIP en disco: {exc}",
        ) from exc
    return TransferBatchResponse(
        batch_id=batch_id,
        mode="zip",
        path=str(target),
        files_count=1,
        bytes=len(zip_bytes),
    )


def _extract_zip(
    batch_id: int,
    destination: Path,
    zip_bytes: bytes,
) -> TransferBatchResponse:
    target_dir = destination / f"batch_{batch_id}"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo crear el subdirectorio: {exc}",
        ) from exc

    files_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Defensa contra zip-slip: verificamos que cada miembro extraído
            # quede DENTRO de target_dir tras resolve(). zipfile en Python
            # 3.6.2+ ya rechaza paths absolutos y "..", pero hacemos una
            # comprobación adicional defensiva.
            target_resolved = target_dir.resolve()
            for member in zf.namelist():
                extracted = (target_dir / member).resolve()
                if (
                    target_resolved not in extracted.parents
                    and extracted != target_resolved
                ):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Entrada del ZIP fuera del destino: {member}",
                    )
            zf.extractall(target_dir)
            files_count = len(zf.namelist())
    except zipfile.BadZipFile as exc:
        log.warning("ZIP corrupto del SaaS: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"El ZIP recibido no es válido: {exc}",
        ) from exc
    except OSError as exc:
        log.exception("Error extrayendo ZIP a %s", target_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extrayendo el ZIP en disco: {exc}",
        ) from exc

    return TransferBatchResponse(
        batch_id=batch_id,
        mode="extracted",
        path=str(target_dir),
        files_count=files_count,
        bytes=len(zip_bytes),
    )
