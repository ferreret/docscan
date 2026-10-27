"""Icono, acento y etiquetas de la tarjeta de una aplicación en el launcher.

Paridad con FlexibarNET 10 (``AppIconCatalog`` y ``AppCardTagDeriver``): todo
se deriva de forma determinista de la configuración real de la aplicación,
sin campos que mantener. Mismo input, misma tarjeta; un JSON roto nunca
lanza, solo cae al valor por defecto.

DocScan no guarda un icono ni un acento elegidos a mano (Flexibar sí, en
``IconKey``/``IconAccent``): siempre se derivan.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import QCoreApplication, QSettings

from app.services.event_config import has_code
from app.services.transfer_service import parse_transfer_config

log = logging.getLogger(__name__)

# Clave del catálogo de Flexibar → icono Lucide equivalente
ICONS: dict[str, str] = {
    "document": "file-text",
    "pdf": "file-type",
    "scanner": "scan-line",
    "barcode": "barcode",
    "text": "scan-text",
    "clipboard": "clipboard",
    "folder": "folder",
    "cloud": "cloud",
    "image": "image",
    "code": "code",
    "print": "printer",
    "camera": "camera",
}

# Acentos, en el orden de Flexibar: el índice sale del hash del nombre.
ACCENTS: tuple[str, ...] = (
    "blue",
    "green",
    "mauve",
    "peach",
    "yellow",
    "red",
    "orange",
)

MAX_TAGS = 3


@dataclass(frozen=True)
class AppCardInfo:
    """Lo que la tarjeta muestra de una aplicación, ya derivado."""

    icon_key: str
    accent: str
    tags: tuple[str, ...]
    updated: str  # dd/MM/yyyy, o "" si no hay fecha

    @property
    def icon_name(self) -> str:
        """Nombre del icono Lucide."""
        return ICONS.get(self.icon_key, ICONS["document"])


def _tr(text: str) -> str:
    return QCoreApplication.translate("AppCard", text)


def pipeline_step_types(pipeline_json: str | None, app_id: int = 0) -> set[str]:
    """Tipos de paso del pipeline, en minúsculas. Nunca lanza."""
    if not pipeline_json or pipeline_json.strip() in ("", "[]"):
        return set()
    try:
        steps = json.loads(pipeline_json)
    except (json.JSONDecodeError, TypeError) as e:
        log.warning("pipeline_json malformado en la App %s: %s", app_id, e)
        return set()
    if not isinstance(steps, list):
        return set()
    return {
        step["type"].lower()
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("type"), str)
    }


def resolve_accent(name: str | None) -> str:
    """Acento estable a partir del nombre (FNV-1a de 32 bits, como Flexibar).

    El hash recorre las unidades UTF-16 del nombre, igual que un ``string``
    de .NET, así que una App con el mismo nombre tiene el mismo color en los
    dos productos.
    """
    h = 2166136261
    data = (name or "").encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = data[i] | (data[i + 1] << 8)
        h = ((h ^ unit) * 16777619) & 0xFFFFFFFF
    return ACCENTS[h % len(ACCENTS)]


def _transfer_config(app: Any) -> Any | None:
    try:
        return parse_transfer_config(getattr(app, "transfer_json", "") or "{}")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        log.warning("transfer_json malformado en la App %s: %s", app.id, e)
        return None


def _outputs_pdf(app: Any) -> bool:
    cfg = _transfer_config(app)
    if cfg is None:
        return False
    return cfg.mode in ("pdf", "pdfa") or cfg.output_format.lower() == "pdf"


def remembered_scanner(app_id: int) -> str:
    """Escáner que el Workbench recuerda para la aplicación ("" si ninguno).

    Es el equivalente de ``DefaultScannerDeviceName`` de Flexibar. No sirve
    ``scanner_backend``: el Configurador siempre guarda uno (su combo no
    tiene opción vacía), así que todas las aplicaciones parecerían de escáner.
    """
    value = QSettings("DocScanStudio", "Workbench").value(
        f"source/{app_id}/scanner_name", ""
    )
    return value if isinstance(value, str) else ""


def derive_icon_key(app: Any, steps: set[str] | None = None) -> str:
    """Barcode > OCR > salida PDF > escáner elegido > documento."""
    steps = pipeline_step_types(app.pipeline_json, app.id) if steps is None else steps
    if "barcode" in steps:
        return "barcode"
    if "ocr" in steps:
        return "text"
    if _outputs_pdf(app):
        return "pdf"
    if remembered_scanner(app.id).strip():
        return "scanner"
    return "document"


def _has_scripts(app: Any, steps: set[str]) -> bool:
    if "script" in steps:
        return True
    events = (getattr(app, "events_json", "") or "").strip()
    if not events or events == "{}":
        return False
    try:
        data = json.loads(events)
    except json.JSONDecodeError, TypeError:
        return True  # hay algo escrito, aunque no se pueda leer
    if not isinstance(data, dict):
        return False
    return any(has_code(v) for v in data.values())


def format_tag(app: Any) -> str | None:
    """Formato de salida («PDF», «PDF/A», «TIFF», «CSV»…), o None sin transferencia."""
    cfg = _transfer_config(app)
    if cfg is None or not cfg.standard_enabled or not cfg.destination.strip():
        return None
    if cfg.mode == "pdf":
        return "PDF"
    if cfg.mode == "pdfa":
        return "PDF/A"
    if cfg.mode == "csv":
        return "CSV"
    fmt = cfg.output_format or getattr(app, "output_format", "") or "tiff"
    return fmt.upper()


def derive_tags(app: Any, steps: set[str] | None = None) -> tuple[str, ...]:
    """Hasta tres etiquetas: barcodes, OCR, scripts y formato de salida."""
    steps = pipeline_step_types(app.pipeline_json, app.id) if steps is None else steps
    tags: list[str] = []
    if "barcode" in steps:
        tags.append(_tr("Códigos de barras"))
    if "ocr" in steps:
        tags.append("OCR")
    if _has_scripts(app, steps):
        tags.append("Scripts")
    fmt = format_tag(app)
    if fmt:
        tags.append(fmt)
    if not tags:
        tags.append(_tr("Digitalización"))
    return tuple(tags[:MAX_TAGS])


def format_date(value: datetime | None) -> str:
    """Fecha de la tarjeta (dd/MM/yyyy, como Flexibar)."""
    return value.strftime("%d/%m/%Y") if isinstance(value, datetime) else ""


def card_info(app: Any) -> AppCardInfo:
    """Deriva todo lo que la tarjeta necesita de una aplicación del ORM."""
    steps = pipeline_step_types(app.pipeline_json, app.id)
    return AppCardInfo(
        icon_key=derive_icon_key(app, steps),
        # Un color fijado en el Configurador gana al automático por el nombre
        accent=(
            app.icon_accent
            if getattr(app, "icon_accent", "") in ACCENTS
            else resolve_accent(app.name)
        ),
        tags=derive_tags(app, steps),
        updated=format_date(getattr(app, "updated_at", None) or app.created_at),
    )
