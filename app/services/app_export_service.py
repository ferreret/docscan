"""Servicio de exportacion/importacion de aplicaciones como JSON.

Exporta una aplicacion completa a un fichero .docscan (JSON legible)
e importa desde fichero, gestionando colisiones de nombre.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.repositories.application_repo import ApplicationRepository
from app.models.application import Application

log = logging.getLogger(__name__)

EXPORT_VERSION = 1

# Campos configurables que se exportan/importan.
# Excluye: id, created_at, updated_at (DB-specific).
_EXPORTABLE_FIELDS: list[str] = [
    "name",
    "description",
    "active",
    "pipeline_json",
    "events_json",
    "transfer_json",
    "batch_fields_json",
    "index_fields_json",
    "image_config_json",
    "ai_config_json",
    "auto_transfer",
    "close_after_transfer",
    "background_color",
    "output_format",
    "default_tab",
    "scanner_backend",
]

# Campos JSON que se parsean a objeto para legibilidad del export.
_JSON_FIELDS: list[str] = [
    "pipeline_json",
    "events_json",
    "transfer_json",
    "batch_fields_json",
    "index_fields_json",
    "image_config_json",
    "ai_config_json",
]


class AppImportError(Exception):
    """Error durante la importacion de una aplicacion."""


def export_application(app: Application) -> dict[str, Any]:
    """Exporta una aplicacion a un diccionario JSON-serializable.

    Los campos JSON internos se parsean a objetos Python para
    que el fichero exportado sea legible y editable.
    """
    app_data: dict[str, Any] = {}
    for field_name in _EXPORTABLE_FIELDS:
        value = getattr(app, field_name, None)
        if field_name in _JSON_FIELDS and isinstance(value, str):
            try:
                value = json.loads(value) if value else None
            except json.JSONDecodeError:
                pass
        app_data[field_name] = value

    return {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "application": app_data,
    }


def export_to_file(app: Application, path: str | Path) -> None:
    """Exporta una aplicacion a un fichero JSON."""
    data = export_application(app)
    path = Path(path)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Aplicacion '%s' exportada a %s", app.name, path)


def validate_import_data(data: dict[str, Any]) -> list[str]:
    """Valida la estructura de un fichero de importacion.

    Returns:
        Lista de errores (vacia si es valido).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["El fichero no contiene un objeto JSON valido."]

    version = data.get("version")
    if version is None:
        errors.append("Falta el campo 'version'.")
    elif version != EXPORT_VERSION:
        errors.append(
            f"Version no soportada: {version} (esperada: {EXPORT_VERSION})."
        )

    app_data = data.get("application")
    if app_data is None:
        errors.append("Falta el campo 'application'.")
    elif not isinstance(app_data, dict):
        errors.append("El campo 'application' debe ser un objeto.")
    else:
        if not app_data.get("name"):
            errors.append("Falta el nombre de la aplicacion.")

    return errors


def import_application(
    data: dict[str, Any],
    session: Any,
    name_override: str | None = None,
) -> Application:
    """Importa una aplicacion desde datos JSON.

    No hace commit — el llamador controla la transaccion.

    Args:
        data: Diccionario con estructura {version, application}.
        session: Sesion SQLAlchemy activa.
        name_override: Nombre alternativo (si hay colision).

    Returns:
        Application creada (sin commit).

    Raises:
        AppImportError: Si los datos no son validos.
    """
    errors = validate_import_data(data)
    if errors:
        raise AppImportError("\n".join(errors))

    app_data = data["application"]
    repo = ApplicationRepository(session)

    # Resolver nombre
    name = name_override or app_data["name"]
    if repo.get_by_name(name):
        name = _unique_name(name, repo)

    # Construir Application
    app = Application(name=name)
    app.description = app_data.get("description", "")
    app.active = app_data.get("active", True)

    # Campos JSON: re-serializar si vienen como objeto
    for field_name in _JSON_FIELDS:
        value = app_data.get(field_name)
        if value is not None:
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            setattr(app, field_name, value)

    # Campos escalares
    for field_name in (
        "auto_transfer", "close_after_transfer", "background_color",
        "output_format", "default_tab", "scanner_backend",
    ):
        value = app_data.get(field_name)
        if value is not None:
            setattr(app, field_name, value)

    repo.save(app)
    log.info("Aplicacion '%s' importada desde JSON.", name)
    return app


def _unique_name(base_name: str, repo: ApplicationRepository) -> str:
    """Genera un nombre unico añadiendo sufijo."""
    candidate = f"{base_name} (importada)"
    if not repo.get_by_name(candidate):
        return candidate
    counter = 2
    while True:
        candidate = f"{base_name} (importada {counter})"
        if not repo.get_by_name(candidate):
            return candidate
        counter += 1
