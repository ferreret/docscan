"""Lectura y escritura de las entradas de ``Application.events_json``.

Cada evento admite dos formas, igual que el worker desde siempre:

- ``"código"``: el script a secas (forma histórica, siempre activado).
- ``{"script": "código", "enabled": false, "entry_point": "…"}``: forma
  extendida. ``enabled`` es la casilla «Activado» de la pestaña Eventos
  (paridad FlexibarNET10: un evento PAUSADO conserva el código pero no se
  ejecuta); si falta, el evento está activado.

Todo el que lea ``events_json`` (Workbench, worker, ``--direct-mode``,
``init_global`` del launcher, panel de verificación) pasa por aquí, de modo
que un evento desactivado no se compila y por tanto no corre en ningún sitio:
``ScriptEngine.run_event*`` y ``transfer_flow`` solo ejecutan lo compilado.
"""

from __future__ import annotations

import json
from typing import Any


def event_source(config: Any) -> str:
    """Código del evento, en cualquiera de las dos formas ("" si no hay)."""
    if isinstance(config, str):
        return config
    if isinstance(config, dict):
        source = config.get("script", "")
        return source if isinstance(source, str) else ""
    return ""


def event_enabled(config: Any) -> bool:
    """True salvo que la entrada diga ``"enabled": false``."""
    if isinstance(config, dict):
        return config.get("enabled", True) is not False
    return True


def event_entry_point(name: str, config: Any) -> str:
    """Función a llamar: ``entry_point`` de la forma extendida o el nombre."""
    if isinstance(config, dict):
        entry = config.get("entry_point")
        if isinstance(entry, str) and entry.strip():
            return entry
    return name


def has_code(config: Any) -> bool:
    """True si la entrada tiene código, esté o no activada."""
    return bool(event_source(config).strip())


def make_event_entry(previous: Any, source: str, enabled: bool) -> Any:
    """Entrada a guardar para un evento con ``source`` y la casilla ``enabled``.

    Un evento activado sin más claves se guarda como texto, la forma de
    siempre, para que el JSON no cambie en las Apps que no usan la casilla.
    Si la entrada ya era un dict (con ``entry_point`` u otras claves), se
    conservan sus claves y solo se actualizan ``script`` y ``enabled``.
    """
    if isinstance(previous, dict):
        entry = dict(previous)
        entry["script"] = source
        if enabled:
            entry.pop("enabled", None)
        else:
            entry["enabled"] = False
        return entry
    if enabled:
        return source
    return {"script": source, "enabled": False}


def parse_events(events_json: str | None) -> dict[str, Any]:
    """``events_json`` como dict; vacío si no se puede leer."""
    try:
        data = json.loads(events_json or "{}")
    except json.JSONDecodeError, TypeError:
        return {}
    return data if isinstance(data, dict) else {}


def active_event_sources(events_json: str | None) -> dict[str, str]:
    """``{evento: código}`` de los eventos activados y con código."""
    return {
        name: event_source(config)
        for name, config in parse_events(events_json).items()
        if has_code(config) and event_enabled(config)
    }
