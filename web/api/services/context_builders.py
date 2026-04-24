"""Funciones compartidas para construir contextos del pipeline a partir de modelos ORM.

Centraliza la lógica de mapeo ORM → context dataclasses para evitar
duplicación entre ``event_dispatcher`` y ``pipeline_runner``.
"""

from __future__ import annotations

import json

from app.models.application import Application
from app.models.batch import Batch
from app.pipeline.page_context import AppContext, BatchContext


def build_app_context(application: Application) -> AppContext:
    """Mapea Application ORM → AppContext del pipeline."""
    return AppContext(
        id=application.id,
        name=application.name,
        description=application.description,
        output_format=application.output_format,
        auto_transfer=application.auto_transfer,
    )


def build_batch_context(batch: Batch) -> BatchContext:
    """Mapea Batch ORM → BatchContext del pipeline."""
    try:
        fields = json.loads(batch.fields_json) if batch.fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    return BatchContext(
        id=batch.id,
        fields=fields,
        state=batch.state,
        page_count=batch.page_count,
        folder_path=batch.folder_path,
        hostname=batch.hostname,
    )
