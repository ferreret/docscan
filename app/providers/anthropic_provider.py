"""Proveedor de IA Anthropic (Claude Vision)."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import cv2
import numpy as np

from app.providers.base_provider import BaseProvider

log = logging.getLogger(__name__)

# Timeout para llamadas API (segundos)
_API_TIMEOUT = 60
# Reintentos para rate-limit
_RATE_LIMIT_RETRIES = 1
_RATE_LIMIT_DELAY = 2.0


class ProviderError(Exception):
    """Error irrecuperable del proveedor de IA."""


class AnthropicProvider(BaseProvider):
    """Extracción y clasificación con Claude Vision.

    Args:
        api_key: Clave API de Anthropic.
        model: Modelo a usar (default: claude-sonnet-4-20250514).
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=_API_TIMEOUT,
            )
        return self._client

    def extract_fields(
        self,
        image: Any,
        prompt: str,
        fields: list[dict[str, str]],
    ) -> dict[str, str]:
        client = self._get_client()
        b64 = _image_to_base64(image)

        fields_desc = "\n".join(
            f"- {f['name']} ({f.get('type', 'text')}): {f.get('description', '')}"
            for f in fields
        )

        system_prompt = (
            "Eres un extractor de datos de documentos. "
            "Responde SOLO con un JSON válido con los campos solicitados. "
            "Si no puedes extraer un campo, usa cadena vacía."
        )

        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            },
            {
                "type": "text",
                "text": f"{prompt}\n\nCampos a extraer:\n{fields_desc}",
            },
        ]

        try:
            response = _call_with_retry(
                lambda: client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_content}],
                )
            )
        except Exception as e:
            log.error("Error API Anthropic (extract_fields): %s", e)
            return {f["name"]: "" for f in fields}

        if not response.content:
            log.warning("Respuesta vacía de Anthropic (extract_fields)")
            return {f["name"]: "" for f in fields}

        return _parse_json_response(response.content[0].text, fields)

    def classify_document(
        self,
        image: Any,
        classes: list[str],
    ) -> str:
        client = self._get_client()
        b64 = _image_to_base64(image)

        classes_str = ", ".join(classes)
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            },
            {
                "type": "text",
                "text": (
                    f"Clasifica este documento en una de las siguientes "
                    f"categorías: {classes_str}. "
                    f"Responde SOLO con el nombre de la categoría."
                ),
            },
        ]

        try:
            response = _call_with_retry(
                lambda: client.messages.create(
                    model=self._model,
                    max_tokens=50,
                    messages=[{"role": "user", "content": user_content}],
                )
            )
        except Exception as e:
            log.error("Error API Anthropic (classify_document): %s", e)
            return ""

        if not response.content:
            log.warning("Respuesta vacía de Anthropic (classify_document)")
            return ""

        result = response.content[0].text.strip()
        # Buscar la mejor coincidencia
        for cls in classes:
            if cls.lower() in result.lower():
                return cls
        return result


class OpenAIProvider(BaseProvider):
    """Extracción y clasificación con OpenAI GPT-4o Vision.

    Args:
        api_key: Clave API de OpenAI.
        model: Modelo a usar (default: gpt-4o).
    """

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import openai
            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=_API_TIMEOUT,
            )
        return self._client

    def extract_fields(
        self,
        image: Any,
        prompt: str,
        fields: list[dict[str, str]],
    ) -> dict[str, str]:
        client = self._get_client()
        b64 = _image_to_base64(image)

        fields_desc = "\n".join(
            f"- {f['name']} ({f.get('type', 'text')}): {f.get('description', '')}"
            for f in fields
        )

        try:
            response = _call_with_retry(
                lambda: client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un extractor de datos de documentos. "
                                "Responde SOLO con un JSON válido."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64}",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": f"{prompt}\n\nCampos a extraer:\n{fields_desc}",
                                },
                            ],
                        },
                    ],
                    max_tokens=1024,
                )
            )
        except Exception as e:
            log.error("Error API OpenAI (extract_fields): %s", e)
            return {f["name"]: "" for f in fields}

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return {f["name"]: "" for f in fields}

        return _parse_json_response(content, fields)

    def classify_document(
        self,
        image: Any,
        classes: list[str],
    ) -> str:
        client = self._get_client()
        b64 = _image_to_base64(image)

        classes_str = ", ".join(classes)
        try:
            response = _call_with_retry(
                lambda: client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64}",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"Clasifica este documento: {classes_str}. "
                                        f"Responde SOLO con el nombre de la categoría."
                                    ),
                                },
                            ],
                        },
                    ],
                    max_tokens=50,
                )
            )
        except Exception as e:
            log.error("Error API OpenAI (classify_document): %s", e)
            return ""

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return ""

        result = content.strip()
        for cls in classes:
            if cls.lower() in result.lower():
                return cls
        return result


# ------------------------------------------------------------------
# Utilidades compartidas
# ------------------------------------------------------------------


def _image_to_base64(image: Any) -> str:
    """Convierte una imagen ndarray a base64 PNG."""
    if isinstance(image, str):
        return image  # Ya es base64
    if isinstance(image, bytes):
        return base64.b64encode(image).decode()

    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("No se pudo codificar la imagen a PNG")
    return base64.b64encode(buffer).decode()


def _call_with_retry(fn, retries: int = _RATE_LIMIT_RETRIES):
    """Ejecuta fn() con retry para rate-limit.

    Reintenta una vez con delay si se detecta rate-limit.
    Propaga otras excepciones directamente.
    """
    for attempt in range(1 + retries):
        try:
            return fn()
        except Exception as e:
            error_type = type(e).__name__
            is_rate_limit = "rate" in error_type.lower() or "429" in str(e)
            if is_rate_limit and attempt < retries:
                log.warning(
                    "Rate limit detectado, reintentando en %.1fs...",
                    _RATE_LIMIT_DELAY,
                )
                time.sleep(_RATE_LIMIT_DELAY)
                continue
            raise


def _parse_json_response(
    text: str,
    fields: list[dict[str, str]],
) -> dict[str, str]:
    """Extrae JSON de la respuesta del modelo."""
    # Intentar parsear directamente
    text = text.strip()
    # Limpiar bloques markdown
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {f["name"]: str(data.get(f["name"], "")) for f in fields}
    except json.JSONDecodeError:
        pass

    log.warning("No se pudo parsear JSON de la respuesta IA: %s", text[:200])
    return {f["name"]: "" for f in fields}
