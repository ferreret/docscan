"""Documento lógico: el tramo de páginas que va de un separador al siguiente.

Paridad con FlexibarNET10 (``DocumentGrouper``): el separador es una
propiedad de la página (``is_separator`` + ``separator_value``) y el
documento se calcula al vuelo, nunca se almacena. Flexibar llegó a este
modelo tras abandonar uno con entidad ``Document`` propia (v0.5.0).

Reglas:

- Las páginas anteriores al primer separador forman un documento implícito.
- Un lote sin separadores es un único documento.
- Reordenar recalcula los tramos, porque la marca viaja con la página.

Dominio puro: funciona con cualquier objeto que tenga ``is_separator``,
``separator_value`` y ``page_index`` (modelo ORM, ``PageContext`` o el dict
de la transferencia).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


def _get(page: Any, name: str, default: Any = None) -> Any:
    """Lee un atributo de una página, sea objeto o dict."""
    if isinstance(page, dict):
        return page.get(name, default)
    return getattr(page, name, default)


def page_is_separator(page: Any) -> bool:
    """¿La página abre un documento?"""
    return bool(_get(page, "is_separator", False))


def page_separator_value(page: Any) -> str:
    """Valor de separador de la página (``""`` si no tiene)."""
    return str(_get(page, "separator_value", "") or "")


@dataclass(frozen=True)
class LogicalDocument:
    """Documento lógico de un lote.

    Attributes:
        index: Posición del documento en el lote, empezando en 1.
        separator_page: Página separadora, o None en el documento implícito
            inicial (páginas antes del primer separador).
        pages: Páginas del documento en orden, separadora incluida.
    """

    index: int
    separator_page: Any | None
    pages: list[Any] = field(default_factory=list)

    @property
    def is_implicit(self) -> bool:
        """True si es el documento inicial sin página separadora."""
        return self.separator_page is None

    @property
    def separator_value(self) -> str:
        """Valor del separador del documento (``""`` en el implícito)."""
        if self.separator_page is None:
            return ""
        return page_separator_value(self.separator_page)

    @property
    def fields(self) -> dict[str, Any]:
        """Campos del documento: los de su página separadora."""
        if self.separator_page is None:
            return {}
        return dict(_get(self.separator_page, "fields", None) or {})


def split_documents(pages: Sequence[Any]) -> list[LogicalDocument]:
    """Agrupa las páginas en documentos lógicos.

    Args:
        pages: Páginas en el orden del lote.

    Returns:
        Documentos en orden. Lista vacía si no hay páginas.
    """
    documents: list[LogicalDocument] = []
    current: list[Any] = []
    separator: Any | None = None

    def close() -> None:
        if current:
            documents.append(
                LogicalDocument(
                    index=len(documents) + 1,
                    separator_page=separator,
                    pages=list(current),
                )
            )

    for page in pages:
        if page_is_separator(page):
            close()
            current = [page]
            separator = page
        else:
            current.append(page)
    close()
    return documents
