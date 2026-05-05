"""Paginación genérica para endpoints de listado."""

from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    """Parámetros de paginación (limit + offset).

    ``limit`` máximo 200 para evitar que un cliente fuerce respuestas gigantes;
    ``offset`` sin tope superior, el cliente es responsable de no pedir más
    allá de ``total``.
    """

    limit: int = 50
    offset: int = 0


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta estándar de un endpoint paginado."""

    items: list[T]
    total: int
    limit: int
    offset: int
