"""Clase base abstracta para proveedores de IA (Strategy pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Proveedor de extracción/clasificación por IA.

    Cada proveedor implementa los métodos de extracción de campos
    y clasificación de documentos.
    """

    @abstractmethod
    def extract_fields(
        self,
        image: Any,
        prompt: str,
        fields: list[dict[str, str]],
    ) -> dict[str, str]:
        """Extrae campos estructurados de una imagen.

        Args:
            image: Imagen como ndarray o base64.
            prompt: Prompt con instrucciones de extracción.
            fields: Lista de campos esperados
                [{"name": "...", "type": "...", "description": "..."}].

        Returns:
            Diccionario {nombre_campo: valor_extraído}.
        """

    @abstractmethod
    def classify_document(
        self,
        image: Any,
        classes: list[str],
    ) -> str:
        """Clasifica un documento en una de las clases dadas.

        Args:
            image: Imagen como ndarray o base64.
            classes: Lista de clases posibles.

        Returns:
            Nombre de la clase asignada.
        """
