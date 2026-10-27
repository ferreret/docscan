"""Orden y visibilidad del panel derecho del Workbench, por aplicación.

Paridad con FlexibarNET 10 (``WorkbenchTabsLayout``): el panel derecho apila
dos paneles fijos (barcodes de la página y campos de lote), siempre arriba y
en ese orden, y debajo un bloque de pestañas (Verificación, OCR, Log) cuyo
orden y visibilidad decide cada aplicación. Se persiste como JSON en
``Application.workbench_layout_json``; vacío o inválido = valores por
defecto (todo visible, orden histórico).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BARCODES = "barcodes"
CAMPOS = "campos"
VERIFICACION = "verificacion"
OCR = "ocr"
LOG = "log"

# Paneles fijos: van siempre al principio y en este orden (no se reordenan).
PANEL_IDS: tuple[str, ...] = (BARCODES, CAMPOS)
# Pestañas reordenables, en su orden por defecto.
TAB_IDS: tuple[str, ...] = (VERIFICACION, OCR, LOG)
ALL_IDS: tuple[str, ...] = PANEL_IDS + TAB_IDS

# Valores antiguos de ``Application.default_tab``. «lote» era la pestaña de
# campos, que ahora es un panel: se abre la primera pestaña visible.
_LEGACY_DEFAULT_TAB = {"lote": "", "log": LOG}


@dataclass(frozen=True)
class LayoutEntry:
    """Una entrada del panel derecho."""

    id: str
    visible: bool = True


@dataclass(frozen=True)
class WorkbenchLayout:
    """Orden y visibilidad de paneles y pestañas del panel derecho."""

    entries: tuple[LayoutEntry, ...]

    @classmethod
    def default(cls) -> WorkbenchLayout:
        """Todo visible, en el orden histórico."""
        return cls(tuple(LayoutEntry(i) for i in ALL_IDS))

    @classmethod
    def from_json(cls, raw: str | None) -> WorkbenchLayout:
        """Lee el JSON persistido, tolerando datos viejos o incompletos.

        Ignora ids desconocidos y duplicados, añade como visibles los que
        falten y coloca siempre los paneles fijos al principio.
        """
        if not raw or not raw.strip():
            return cls.default()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return cls.default()
        if not isinstance(data, list):
            return cls.default()

        seen: dict[str, LayoutEntry] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            entry_id = item.get("id")
            if entry_id in ALL_IDS and entry_id not in seen:
                seen[entry_id] = LayoutEntry(entry_id, bool(item.get("visible", True)))
        tabs = [seen[i] for i in seen if i in TAB_IDS]
        tabs += [LayoutEntry(i) for i in TAB_IDS if i not in seen]
        panels = [seen.get(i, LayoutEntry(i)) for i in PANEL_IDS]
        return cls(tuple(panels + tabs))

    def to_json(self) -> str:
        """JSON para ``Application.workbench_layout_json``."""
        return json.dumps(
            [{"id": e.id, "visible": e.visible} for e in self.entries],
            ensure_ascii=False,
        )

    def is_visible(self, entry_id: str) -> bool:
        """¿Está visible el panel o la pestaña ``entry_id``?"""
        return next((e.visible for e in self.entries if e.id == entry_id), True)

    def visible_tabs(self) -> list[str]:
        """Pestañas visibles, en su orden."""
        return [e.id for e in self.entries if e.id in TAB_IDS and e.visible]

    def initial_tab(self, default_tab: str | None) -> str | None:
        """Pestaña que debe quedar activa al abrir el Workbench.

        La configurada si existe y está visible; si no, la primera visible;
        ``None`` si no hay ninguna pestaña visible.
        """
        visible = self.visible_tabs()
        wanted = (default_tab or "").strip().lower()
        wanted = _LEGACY_DEFAULT_TAB.get(wanted, wanted)
        if wanted in visible:
            return wanted
        return visible[0] if visible else None
