"""Servicio de IA — fachada sobre los proveedores.

Resuelve el proveedor y la plantilla, y ejecuta la extracción
o clasificación.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.providers.base_provider import BaseProvider
from app.services.ocr_service import OcrService

log = logging.getLogger(__name__)


class AiService:
    """Fachada de IA que despacha a proveedores concretos.

    Args:
        providers: Diccionario {nombre: BaseProvider}.
        ocr_service: Servicio OCR para el proveedor "local_ocr".
        template_loader: Callable que carga una plantilla por ID.
    """

    def __init__(
        self,
        providers: dict[str, BaseProvider] | None = None,
        ocr_service: OcrService | None = None,
        template_loader: Any = None,
    ) -> None:
        self._providers = providers or {}
        self._ocr_service = ocr_service
        self._template_loader = template_loader

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        """Registra un proveedor de IA."""
        self._providers[name] = provider

    def extract(
        self,
        image: np.ndarray,
        provider: str,
        template_id: int | None = None,
        page: Any = None,
        batch: Any = None,
        app: Any = None,
    ) -> dict[str, str]:
        """Extrae campos de una imagen usando el proveedor indicado.

        Args:
            image: Imagen de entrada.
            provider: Nombre del proveedor ("anthropic", "openai", "local_ocr").
            template_id: ID de la plantilla de extracción.
            page, batch, app: Contextos para interpolación del prompt.

        Returns:
            Diccionario {nombre_campo: valor}.
        """
        # Caso especial: local_ocr usa el servicio OCR
        if provider == "local_ocr":
            return self._extract_local(image, template_id)

        prov = self._providers.get(provider)
        if prov is None:
            raise ValueError(f"Proveedor de IA no configurado: '{provider}'")

        template = self._load_template(template_id)
        if template is None:
            raise ValueError(
                f"Plantilla {template_id} no encontrada"
            )

        prompt = template.get("prompt", "")
        fields = template.get("fields", [])

        # Interpolar variables en el prompt
        if page or batch or app:
            try:
                prompt = prompt.format(page=page, batch=batch, app=app)
            except (AttributeError, KeyError, IndexError):
                pass  # Usar prompt sin interpolar

        return prov.extract_fields(image, prompt, fields)

    def classify(
        self,
        image: np.ndarray,
        provider: str,
        classes: list[str],
    ) -> str:
        """Clasifica un documento.

        Args:
            image: Imagen de entrada.
            provider: Nombre del proveedor.
            classes: Lista de clases posibles.

        Returns:
            Clase asignada.
        """
        prov = self._providers.get(provider)
        if prov is None:
            raise ValueError(f"Proveedor de IA no configurado: '{provider}'")
        return prov.classify_document(image, classes)

    def _extract_local(
        self,
        image: np.ndarray,
        template_id: int | None,
    ) -> dict[str, str]:
        """Extracción local usando OCR (sin API externa)."""
        if self._ocr_service is None:
            log.error("OcrService no configurado para local_ocr")
            return {}

        text = self._ocr_service.recognize(image, engine="rapidocr")
        template = self._load_template(template_id)

        if template is None:
            return {"ocr_text": text}

        # Devolver el texto OCR asociado a cada campo
        fields = template.get("fields", [])
        return {f["name"]: text for f in fields}

    def _load_template(self, template_id: int | None) -> dict | None:
        """Carga una plantilla por ID."""
        if template_id is None:
            return None
        if self._template_loader is not None:
            return self._template_loader(template_id)
        return None
